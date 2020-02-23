<p align="center">
  <img src="watcher.png" alt="watcher" height="372px">
</p>
<h1 style="font-size: 56px; margin: 0; padding: 0;" align="center">
  watcher
</h1>
<p align="center">
  <img src="https://img.shields.io/badge/python-3.8-blue.svg" alt="Python 3.8">
  <img src="http://public.serverless.com/badges/v3.svg" alt="Serverless">
  <img src="https://img.shields.io/badge/code%20style-black-000000.svg" alt="Black">
</p>

## Table of Contents

| Directory | Info |
|:----------|:-----|
| [`lambda/`](../lambdas) | Lambda function(s) source code and associated tests |
| [`layers/`](../layers) | Package directories containing Dockerfiles for generating lambda layer artifacts |

## Conventions

This repository uses the following tools and conventions:

- [serverless](https://serverless.com/) for managing AWS Lambda functions
- [pipenv](https://github.com/pypa/pipenv) for managing Python dependencies and development environment
- Python 3.8
  - [flake8](https://github.com/PyCQA/flake8) for Python linting and static code analysis
  - [isort](https://github.com/timothycrosley/isort) for Python import statement formatting
  - [black](https://github.com/ambv/black) for Python code formatting

## Getting Started

The following instructions will help you get setup for development and testing purposes.

### Prerequisites

#### [NPM](https://github.com/npm/cli)

The `serverless` framework is a Nodejs application used for resource deployment and requires `npm` (>=10.x). See [here](https://serverless.com/framework/docs/providers/aws/guide/quick-start/) for more details about the framework.

The recommended way to install the framework is globally via npm:

```bash
  $ npm i serverless -g
```

However, if you run into issues where you have multiple projects that encounter version conflicts, you can use the locally installed version which is located at `./node_modules/serverless/bin/serverless`

Install the projects deployment dependencies locally by running the following command.

```bash
  $ npm i
```

#### [Pipenv](https://github.com/pypa/pipenv)

Pipenv is used to manage the python dependencies.

Install the projects Python dependencies (with development dependencies) locally by running the following command.

```bash
  $ make setup
```

### Common Commands

Use the `make help` command to view prepared commands for use within this codebase. Make is your friend, make will help
