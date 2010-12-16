#!/bin/sh

export SOFTWARE_CENTER_REVIEWS_HOST="http://184.82.116.62"


# sso
export USOC_SERVICE_URL="https://login.staging.ubuntu.com/api/1.0"
killall ubuntu-sso-login
python /usr/lib/ubuntu-sso-client/ubuntu-sso-login &

# s-c
export PYTHONPATH=$(pwd)
./software-center
