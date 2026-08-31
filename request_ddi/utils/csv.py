# -- STDLIB
import csv


def read_csv_file(csv_lines):
    """Reads CSV file content and returns reader"""
    sample = "\n".join(csv_lines[:2])
    sniffer = csv.Sniffer()
    delimiter = sniffer.sniff(sample).delimiter
    return csv.DictReader(csv_lines, delimiter=delimiter)
