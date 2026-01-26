module.exports = [
  {
    files: ["src/**/*.{js,jsx}"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      parser: require("@babel/eslint-parser"),
      parserOptions: {
        requireConfigFile: false,
        babelOptions: {
          presets: ["@babel/preset-react"],
        },
      },
      globals: {
        browser: true,
        es2022: true,
        node: true,
      },
    },
    settings: {
      react: {
        version: "18.2",
      },
    },
    plugins: {
      react: require("eslint-plugin-react"),
      "react-hooks": require("eslint-plugin-react-hooks"),
    },
    rules: {
      "react/react-in-jsx-scope": "off",
      "no-unused-vars": "warn",
      "no-console": "warn",
      ...require("eslint-plugin-react").configs.recommended.rules,
      ...require("eslint-plugin-react-hooks").configs.recommended.rules,
    },
  },
];
