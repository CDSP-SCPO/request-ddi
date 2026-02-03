import { defineConfig } from "eslint/config";
import js from "@eslint/js";
import stylistic from '@stylistic/eslint-plugin'
import globals from "globals";

export default defineConfig([
	{
		files: ["**/*.js"],
		plugins: {
			js,
			"@stylistic": stylistic
		},
		extends: ["js/recommended"],
		rules: {
			"no-unused-vars": "warn",
			"no-undef": "warn",
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

