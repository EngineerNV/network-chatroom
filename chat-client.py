# Created By Nicholas Vaughn  Computer Networking ECPE 177	10/12/2017
from socket import *
import sys
import threading 
import time 
clientSocket = 0 #this needs to be global to be used by all the threads 
recFlag = True # this will be used to turn off and on our socket receiver for server
 
def initClient(): # this will initialize the client  and socket 
	global clientSocket
	serverName = 'cyberlab.pacific.edu'#input('Please Input Server Hostname: ')#'cyberlab.pacific.edu'
	serverPort = '12000'#input('Please input Server Port #: ')#'12000'
	serverPort = int(serverPort)
	#creating the socket
	try:
		clientSocket = socket(AF_INET, SOCK_STREAM)
		clientSocket.connect((serverName,serverPort))
	except: #catching the error so we can print out one line instead of having the default error
		print('ERROR: Could not connect to Host, Please recheck information or if server is active')
		sys.exit(0)
	 	
	sentence = 'HELLO'
	clientSocket.send(sentence.encode())
	modifiedSentence = clientSocket.recv(1024)
	
		
	
	while 1: # we are looping so that if the input isnt authorized we will ask the user to reenter data
		userName = input('Please Enter a user name:')#'test1'
		userPassword = input('Please Enter Password:')#'p000'
		auth = 'AUTH:'+ userName + ':' + userPassword	#combining strings
		sentence = auth 
		clientSocket.send(sentence.encode())
		modifiedSentence = clientSocket.recv(1024)
		mesg = modifiedSentence.decode()#save computation
		
		print ('From Server:', mesg)
		if 'YES' in mesg:
			break
		print("Authorization Failed: BAD INPUT")
			  
	print('You are now authenticated!')

def serverRec(): # this will revceive messages from the server, and search for strings that make them more user friendly 
	global clientSocket
	global recFlag
	while recFlag:
		data = clientSocket.recv(1024)
		dataStr = data.decode();
		if 'SIGNOFF' in dataStr:
			h,t = dataStr.split(':')
			t,n = t.split('\n') #takes away new line character
			print(t,'just signed off')
			continue
		elif 'SIGNIN' in dataStr:
			h,t = dataStr.split(':')
			t,n = t.split('\n') #takes away new line character
			print(t,'just signed on')
			continue
		elif 'FROM' in dataStr:
			f,usr,msg = dataStr.split(':')
			msg,n = msg.split('\n')
			print('Message from', usr+':', msg)
			continue 
		print('\n',data.decode())

def clientOps(): # this will give the user options to send commands to the server 
	global recFlag
	global clientSocket
	time.sleep(.2)
	while 1:
		print('\n1. List online users')
		print('2. Send someone a message')
		print('3. Sign off')
		opt = input('Choose an option: ')
		if opt == '1':
			sentence = 'LIST'
			print('Users that are currently logged in:')
			clientSocket.send(sentence.encode())
			time.sleep(.1)
		elif opt == '2':
			user = input('User to send message to: ')
			mesg = input('Message: ')
			sentence = 'TO:'+user+':'+mesg
			clientSocket.send(sentence.encode())
			print('Message Sent!')
			time.sleep(.1)
		elif opt == '3':
			sentence = 'BYE'
			clientSocket.send(sentence.encode())
			recFlag = False # turn off receiver thread
			break
		else:
			print('invalid option try again')		
			
	
	
	

def main():
	global clientSocket
	global recFlag
	initClient()
	t1 = threading.Thread(target=serverRec, args=())
	t2 = threading.Thread(target=clientOps, args=())
	t1.start()
	t2.start()
	t2.join()
	t1.join() 
	clientSocket.close()
	

if __name__ == "__main__":
   main()
