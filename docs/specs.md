# Specifications

Mettaton is a module that allows its users to perform various operations related to the deployment and control of singular game servers using docker swarm technology.

A user of this library should be able to import `mettaton.Mettaton` and simply have it run using methods provided by the object.

## Docker daemon status check

### DAEMON_1_DOCKER_IS_CONNECTED

The user should be able to check the connection status of Mettaton to the docker daemon.

### DAEMON_2_CONNECT

The user should be able to connect to a given docker daemon, preferably locally. The daemon must already be configured to be a leader of a docker swarm where all of the deployment servers will be.

### DAEMON_3_DISCONNECT

The user should be able to disconnect from the docker daemon they previously connected to.

## Server spawning

### SPAWN_1_SPAWN

Given sufficient system ressources, the user should be able to spawn a new server at any time.

### SPAWN_2_ERRORS

The user should be informed of any errors happening during the server spawn process

### SPAWN_3_NETWORK_INFO

The user should be supplied with an address where the game server they deployed is available following a successful deployment.

## Server information

### INFO_1_GENERAL_SERVER_INFO

The user should be able to obtain general information about the network status and health of a given server

### INFO_2_SERVER_LIST

The user should be able to query a list of the servers currently running

### INFO_3_SERVER_IDENTIFIER

The user should be able to identify any of the individual instances of the server running using an identifier provided at spawn

### INFO_4_GAME_LOGS

The user shall be able to read the logs of the game server if or when requested.

## Server shutdown

### SHUTDOWN_1_ANY_TIME

The user should be able to shutdown any server at any point

### SHUTDOWN_2_ERROR

Errors should be transmitted to the user whenever a server deletion does not happen correctly

## Image handling

### IMAGE_1_DEPLOYMENT

The user must be able to provide the name of an image that can either be pulled from known image repositories, or shared from the docker swarm manager.

### IMAGE_2_PORT_CONFIG

Depending on the image being used, the user should be able to provide the list and number of internal ports that must be exposed

## Startup/Shutdown recovery

### RECOVERY_1_STATE_RECOVERY

In case of shutdown, mettaton must be able to save its state to storage. Upon start-up, it must load that state and compare it to the state of the docker swam to determine what is still available to the user, if anything.

The module is not responsible for starting the docker swarm by itself, or adding agents.

## Testing

### TESTS_1_UNITS

Unit tests should be implemented to test as much of the module as possible, including every single API endpoint made available to end users.

## Errors

Are considered errors :
 - Any event happening as a response to an interaction with the docker Daemon that cannot reasonably be mitigated internally by the module and leaves the daemon in a state that was not desired by the user
 - Any unexpected termination of a game server container.

The first type will be transmitted to the end user using Python exceptions. For the latter, which is asynchronous, the module will spawn a watcher thread that preiodically monitors the health of the game servers it manages. If any server were to fail unexpectedly, a message would be sent along in a queue that the user can fetch.
