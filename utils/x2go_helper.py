#!/usr/bin/python
import x2go, gevent, sys, fcntl, os, shlex

def connect(server, port, login, password, session):
    print "PROGRESS: creating"
    cli = x2go.X2goClient(start_pulseaudio=True)
    uuid = cli.register_session(
        server=server,
        port=int(port),
        username=login,
        add_to_known_hosts=True,
        cmd="WEBLIVE",
        geometry="1024x600"
    )
    x2go.defaults.X2GO_DESKTOPSESSIONS['WEBLIVE']="/usr/local/bin/weblive-session %s" % session

    print "PROGRESS: connecting"
    try:
        if cli.connect_session(uuid, password=password) not in (None, True):
            # According to documentation, connect_session may return False
            exception("unable to connect")
    except:
        # Any paramiko exception will get here
        exception("unable to connect")

    print "PROGRESS: starting"
    try:
        if cli.start_session(uuid) not in (None, True):
            # According to documentation, start_session may return False
            exception("unable to start")
    except:
        # Just in case
        exception("unable to start")

    print "CONNECTED"
    return (cli,uuid)

def exception(string):
    print "EXCEPTION: %s" % string
    sys.exit(1)

def disconnect(connection, uuid):
    try:
        if connection.terminate_session(uuid) not in (None, True):
            # According to documentation, connect_session may return False
            exception("unable to disconnect")
    except:
        # Any paramiko exception will get here
        exception("unable to disconnect")

    print "DISCONNECTED"
    sys.exit(0)

# make stdin nonblocking
fd = sys.stdin.fileno()
fl = fcntl.fcntl(fd, fcntl.F_GETFL)
fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

# main loop
connection = None
uuid = None

while 1:
    # Get anything that appeared on stdin
    try:
        buf = sys.stdin.read().strip()
    except IOError:
        buf = None

    if buf:
        params = shlex.split(buf)

        # Parse command from stdin
        if params[0] == "CONNECT:":
            if len(params) == 6:
                connection, uuid = connect(*params[1:])
        elif params[0] == "DISCONNECT":
            if connection and uuid:
                disconnect(connection, uuid)

    # Check if the session ended
    if connection and uuid and not connection.session_ok(uuid):
        disconnect(connection, uuid)

    gevent.sleep(0.5)
