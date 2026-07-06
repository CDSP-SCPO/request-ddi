import { defineConfig } from "eslint/config";
import js from "@eslint/js";
import stylistic from '@stylistic/eslint-plugin'
import unusedImports from "eslint-plugin-unused-imports";
import globals from "globals";

export default defineConfig([
	{
		files: ["**/*.js"],
		plugins: {
			js,
			"unused-imports": unusedImports,
			"@stylistic": stylistic
		},
		extends: ["js/recommended"],
		rules: {
			"no-unused-vars": "error",
			"no-undef": "error",
			"unused-imports/no-unused-imports": "error",
			"no-use-before-define": "warn",
			"no-unreachable": "error",
			"@stylistic/indent": ["error", 2],
			"@stylistic/quotes": ["error", "double"] 
		},
		ignores: ["eslint.config.js"],
		languageOptions: {
			globals: {
				...globals.browser,
				...globals.node,
				...globals.devtools,
			}
		},
	},
]);

