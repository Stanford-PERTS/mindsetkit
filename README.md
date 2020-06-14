mindsetkit
==========

PERTS Mindset Kit

Google AppEngine Jinja2 app

## Release to the public domain

PERTS-created source code has been released to the public domain; see LICENSE.txt.

Content not included can still be found on mindsetkit.org, licensed as CC-BY unless otherwise noted.

## Starting the app locally

You need two processes running to launch the MSK locally; a process that watches for chances to SASS files and compiles them to CSS, and another that runs a webserver. Open two tabs in a Terminal window, and run each of these commands in their own tab.

```
$ npm start
```

and, in the other tab

```
$ npm run server
```

Then open this URL in your browser: `localhost:11080`

## Production builds

Codeship (a continuous integration service) watches the mindsetkit repository on github and builds, tests, and deploys code to mindsetkit.org. Simply committing and syncing to the `master` branch will trigger one of these builds, and your changes will appear on mindsetkit.org a few minutes later.
