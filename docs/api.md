# API

The Mettaton object should allow the user to perform operations described in the specifications document. As such, we currently offer the following API.

## State sanity check

 - `is_connected`
   Checks the connection status of your object with the local daemon.

## Connection

 - `connect`
   Try and connect to the local docker environment. May throw `RuntimeError` if a docker error happens

 - `regain_cluster`
   Try and reconnect to the context of the cluster and reload information like the join token.

 - `get_worker_token`
   Retrieve the token used to add workers to the swarm

## Launching/Stopping servers

 - `launch_server`
   Launch a server with the given image. Not fully implemented Yet.
