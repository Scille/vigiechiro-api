#! /bin/sh

newrelic-admin generate-config $NEWRELIC_LICENSE_KEY newrelic.ini
NEW_RELIC_CONFIG_FILE=newrelic.ini newrelic-admin run-program $@
