import js from "@eslint/js";
import globals from "globals";

export default [
  {
    files: ["portal/**/*.js", "tests/frontend/**/*.js", "scripts/**/*.mjs"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
    rules: {
      ...js.configs.recommended.rules,
      "no-unused-vars": ["error", { "argsIgnorePattern": "^_" }]
    }
  }
];
