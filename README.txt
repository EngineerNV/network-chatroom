Created by Nicholas Vaughn

This program was created with Python 3.5.2 compiler on win32 console

Client side program
------------------------------------
python chat-client.py

If you want to make signing in to the server faster you can hard code the servername and the server port.
Inside of the initClient function 
serverName = input('Please Input Server Hostname: ')#'cyberlab.pacific.edu'
serverPort = input('Please input Server Port #: ')#'12000'

This program is using two threads, one for the client to send information and one to recieve information. 

serverRec() looks for messages from the server, and makes them easier to read with the UI by looking for key words,
and tokenizing the messages.

clientOps() gives options to the user and sends the messages necessary to execute commands

Server Side Program
----------------------------------
python chat-server.py

Most of the code is self explanatory with comments. 
The most important thing to remember is how to set the server port and domain/IP address

Change lines 10 and 11 to customize these two fields respectively 

serverPort = 12000 #change these two variable to have different server hosting ports and IP addresses 
serverAddress = 'localhost'