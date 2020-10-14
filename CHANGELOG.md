# [1.4.0](https://github.com/clowdhaus/watcher/compare/v1.3.0...v1.4.0) (2020-10-14)


### Bug Fixes

* roll back serverless upgrade to 2.4.0 due to breaking IAM role plugin ([41f5e06](https://github.com/clowdhaus/watcher/commit/41f5e064fd4a217cb1a0ea1136a50412026c9967))


### Features

* initial public release of `actions` project ([25cdf35](https://github.com/clowdhaus/watcher/commit/25cdf35342c7f01637685224a6e954d6457e3f9d))
* open source `terraform-aws-datadog-forwarders` module ([bb3697d](https://github.com/clowdhaus/watcher/commit/bb3697d7f743e83dff075c2967d750ce0b52c9ba))

# [1.3.0](https://github.com/clowdhaus/watcher/compare/v1.2.0...v1.3.0) (2020-08-20)


### Features

* add `chunky` to public repos whitelist ([4797a0b](https://github.com/clowdhaus/watcher/commit/4797a0b80cfee06a3c96112eb61f48f1c087333c))
* add dogged-params to public ([dc638c2](https://github.com/clowdhaus/watcher/commit/dc638c2e917e2d6041f313cde38e167c45e9c627))

# [1.2.0](https://github.com/clowdhaus/watcher/compare/v1.1.1...v1.2.0) (2020-04-26)


### Features

* replace custom logging with aws-lambda-powertools logging and tracing ([c753c97](https://github.com/clowdhaus/watcher/commit/c753c97a1bd712ccc473a7ce035315d7d6ca4e02))

## [1.1.1](https://github.com/clowdhaus/watcher/compare/v1.1.0...v1.1.1) (2020-04-24)


### Bug Fixes

* **versions.py:** purge version table before updating during sync operation ([156e937](https://github.com/clowdhaus/watcher/commit/156e937d6820a8535e0c39bddab1d25315d5d928))

# [1.1.0](https://github.com/clowdhaus/watcher/compare/v1.0.2...v1.1.0) (2020-04-23)


### Features

* make `compress` project open source and available to the public ([df2fd29](https://github.com/clowdhaus/watcher/commit/df2fd29d06ffe3895c10a672e1e1063ea4a98fb9))

## [1.0.2](https://github.com/clowdhaus/watcher/compare/v1.0.1...v1.0.2) (2020-03-30)


### Bug Fixes

* **hub.py:** correct order of event precedence logic to capture correct event type ([cf1b6da](https://github.com/clowdhaus/watcher/commit/cf1b6da5c43d40e0376eb8c3cbc02eb57d36ed3e))

## [1.0.1](https://github.com/clowdhaus/watcher/compare/v1.0.0...v1.0.1) (2020-03-29)


### Bug Fixes

* remove unecessary imports, update library dependencies ([bdc68f6](https://github.com/clowdhaus/watcher/commit/bdc68f61759f07971a0d788d97155130430951ce))

# 1.0.0 (2020-03-25)


### Features

* add function to create releases as soon as new tag events are picked up ([0530739](https://github.com/clowdhaus/watcher/commit/05307396c4e6ef48d1b98fd9aec3b3e66a469419))
* add function to sync all repository versions ([a6aca2d](https://github.com/clowdhaus/watcher/commit/a6aca2d673c9a04d6357951dc93c7d08f1874e0a))
* add function to update metadata repo with open pull requests ([46f7a96](https://github.com/clowdhaus/watcher/commit/46f7a961035d541731cc5ba1f43d2b7e17580556))
* add functions for updating/synchronizing all repos on a cadence outside of events ([152ac52](https://github.com/clowdhaus/watcher/commit/152ac523976476548eacd7ad2ecf62e8b176ccce))
* add functions to sync/update repository settings and labels on schedule ([57674a6](https://github.com/clowdhaus/watcher/commit/57674a6e2feb72971977d3cefe880740801c2dae))
* add repository management for new and existing repositories… ([#1](https://github.com/clowdhaus/watcher/issues/1)) ([f77ab28](https://github.com/clowdhaus/watcher/commit/f77ab287803ec3a43ad05470e1a64bdb30b56e8d))
* add scheduled syncing of versions and pull requests on a cadence ([5b04dd1](https://github.com/clowdhaus/watcher/commit/5b04dd16d6c67c25470f648b1dc5b11741ee0742))
* add tag update function to write all tag changes to metadata repository and show latest tags ([b82b349](https://github.com/clowdhaus/watcher/commit/b82b34976e30cb679794f9199c7622d308155e15))
* initial setup of project with validation lambda function ([f5e63a5](https://github.com/clowdhaus/watcher/commit/f5e63a57f63e458d182d8a5034b0a3dfb1dc92ca))
* store pull request data in dynamodb ([963f4b6](https://github.com/clowdhaus/watcher/commit/963f4b6c559ac6aea41f89d615748f224b4099b4))
* store version data in dynamodb ([211a324](https://github.com/clowdhaus/watcher/commit/211a324b977ba832ada814bd5166fe65212469e8))
