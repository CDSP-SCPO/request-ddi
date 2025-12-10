import json
import os
import time

import psycopg2
import requests
from django.contrib.auth import get_user_model
from django.core.management import execute_from_command_line
from django.core.management.base import BaseCommand, CommandError
from django.core.wsgi import get_wsgi_application
from gunicorn.app.wsgiapp import WSGIApplication
from requests.auth import HTTPBasicAuth

from request_ddi.core.documents import BindingSurveyDocument

# Default timeout
DEFAULT_TIMEOUT = 300


class RequestDDIApplication(WSGIApplication):
    """Nicked from https://docs.gunicorn.org/en/latest/custom.html"""

    def __init__(self, app, options=None):
        self.options = options or {}
        self.application = app
        super().__init__()

    def load_config(self):
        config = {
            key: value
            for key, value in self.options.items()
            if key in self.cfg.settings and value is not None
        }
        for key, value in config.items():
            self.cfg.set(key.lower(), value)

    def load(self):
        return self.application


class Command(BaseCommand):
    help = "Bootstraps request_ddi app"

    # Timeout for bootstrap process
    start_time = time.time()

    # Elastic search basic auth
    elasticsearch_basic_auth = HTTPBasicAuth(
        os.environ["ELASTICSEARCH_ADMIN_USER"],
        os.environ["ELASTICSEARCH_ADMIN_PASSWORD"],
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--timeout",
            default=DEFAULT_TIMEOUT,
            nargs="?",
            help="Optional bootstrap timeout period",
        )
        parser.add_argument(
            "--createelasticsearchindex",
            help="Force create elasticsearch index",
            action="store_true",
        )
        parser.add_argument(
            "--ensuresuperuser",
            help="Ensure creation of super user. DJANGO_SUPERUSER* environment variables must be provided.",
            action="store_true",
        )
        parser.add_argument(
            "--startserver",
            help="Start production/development server based on DJANGO_DEBUG environment variable.",
            action="store_true",
        )

    def is_postgres_up(self):
        # Attempt to make a connection to postgres
        try:
            conn = psycopg2.connect(
                host=os.environ["POSTGRES_HOST"],
                port=os.environ["POSTGRES_PORT"],
                user=os.environ["POSTGRES_USER"],
                password=os.environ["POSTGRES_PASSWORD"],
                dbname=os.environ["POSTGRES_DB"],
                connect_timeout=1,
            )
            conn.close()
            return True
        except:  # noqa: E722
            return False

    def bootstrap_postgres(self):
        # Wait for postgres
        while not self.is_postgres_up() and (time.time() - self.start_time < self.timeout):
            time.sleep(5)

        # If postgres is not up within timeout, raise exception
        if not self.is_postgres_up():
            msg = "request_ddi app's bootstrap process timed out waiting for Postgres"
            raise CommandError(msg)

        # Apply DB migrations
        execute_from_command_line(["manage", "migrate"])

    def is_elasticsearch_up(self):
        try:
            response = requests.get(
                f"{os.environ['ELASTICSEARCH_URL']}/_cluster/health?wait_for_status=green&timeout=1s",
                auth=self.elasticsearch_basic_auth,
                timeout=2,
            )
            return response.ok
        except:  # noqa: E722
            return False

    def bootstrap_elasticsearch(self, force_index):
        # Wait for elastic
        while not self.is_elasticsearch_up() and (time.time() - self.start_time < self.timeout):
            time.sleep(3)

        # If postgres is not up within timeout, raise exception
        if not self.is_elasticsearch_up():
            msg = "request_ddi app's bootstrap process timed out waiting for Elasticsearch"
            raise CommandError(msg)

        # Check if elastic search has already indices. If not, create
        try:
            response = requests.get(
                f"{os.environ['ELASTICSEARCH_URL']}/_cat/indices?format=json",
                auth=self.elasticsearch_basic_auth,
                timeout=2,
            )
            data = response.json()
            if not data or force_index:
                execute_from_command_line(["manage", "search_index", "--rebuild", "-f"])
        except:  # noqa: E722
            self.stderr.write(self.style.WARNING("Failed to get indices from Elasticsearch"))

        # Finally update Elasticsearch index
        BindingSurveyDocument().update_index()

    def run_gunicorn_server(self):
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        options = {
            "bind": f"{os.environ.get('REQUEST_DDI_HOST_IP', '0.0.0.0')}:{os.environ.get('REQUEST_DDI_PORT', '8000')}",  # noqa: S104
            "timeout": os.environ.get("REQUEST_DDI_GUNICORN_TIMEOUT", "300"),
            "workers": os.environ.get("REQUEST_DDI_GUNICORN_WORKERS", "2"),
            "threads": os.environ.get("REQUEST_DDI_GUNICORN_THREADS", "1"),
            "loglevel": os.environ.get("REQUEST_DDI_GUNICORN_LOGLEVEL", "info"),
            "accesslog": os.environ.get("REQUEST_DDI_GUNICORN_ACCESSLOG", "-"),
            "errorlog": os.environ.get("REQUEST_DDI_GUNICORN_ERRORLOG", "-"),
        }
        # Extra options from env var
        try:
            extra_opts = json.loads(os.environ.get("REQUEST_DDI_GUNICORN_EXTRA_OPTIONS", "{}"))
        except Exception as e:
            msg = (
                "Invalid value for REQUEST_DDI_GUNICORN_EXTRA_OPTIONS. Must be a valid JSON string"
            )
            raise CommandError(msg) from e
        # Final options after merging default ones with user supplied ones
        options = {
            **options,
            **extra_opts,
        }
        RequestDDIApplication(get_wsgi_application(), options).run()

    def handle(self, *args, **options):
        try:
            self.timeout = int(options["timeout"])
        except ValueError:
            self.stderr.write(
                self.style.WARNING(
                    f"Invalid timeout value {options['timeout']} provided. Using default {DEFAULT_TIMEOUT}"
                )
            )
            self.timeout = DEFAULT_TIMEOUT
        # Bootstrap postgres
        self.bootstrap_postgres()
        # Bootstrap elastic search
        self.bootstrap_elasticsearch(options["createelasticsearchindex"])
        # Ensure to create superuser
        if options["ensuresuperuser"]:
            user = get_user_model()
            if not user.objects.filter(username=os.environ["DJANGO_SUPERUSER_USERNAME"]).exists():
                user.objects.create_superuser(
                    username=os.environ["DJANGO_SUPERUSER_USERNAME"],
                    email=os.environ["DJANGO_SUPERUSER_EMAIL"],
                    password=os.environ["DJANGO_SUPERUSER_PASSWORD"],
                )
                self.stdout.write(self.style.SUCCESS("Super user created successfully"))
        # For production collect static
        if os.environ.get("DJANGO_DEBUG", "false").lower() == "false":
            execute_from_command_line(["manage", "collectstatic", "--noinput"])
            self.stdout.write(self.style.SUCCESS("Collected static assets from apps successfully"))

        self.stdout.write(self.style.SUCCESS("request_ddi bootstraped successfully"))
        # Start web server
        if options["startserver"]:
            if os.environ.get("DJANGO_DEBUG", "false").lower() == "false":
                self.stdout.write(self.style.NOTICE("Starting gunicorn server..."))
                self.run_gunicorn_server()
            else:
                # For backwards compatbility we create a symlink to manage.py
                try:
                    os.symlink(
                        os.path.join(os.getcwd(), "request_ddi", "manage.py"),
                        os.path.join(os.getcwd(), "manage.py"),
                    )
                except FileExistsError:
                    pass
                except Exception as e:
                    msg = "Failed to create symlink to request_ddi/manage.py"
                    raise CommandError(msg) from e
                execute_from_command_line(["manage", "runserver", "0.0.0.0:8000"])
