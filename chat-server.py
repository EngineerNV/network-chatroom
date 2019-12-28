from socket import *
import sys
import threading 
import time 

socketList = [] #this will keep track of users to sockets for sending messages 
online = [] # this will list all the users that are online

def initServer():#this will initialize the server before we start authentication 
	serverPort = 12000 #change these two variable to have different server hosting ports and IP addresses 
	serverAddress = 'localhost'
	try: # seeing if we can create socket
		serverSocket = socket(AF_INET,SOCK_STREAM)
		serverSocket.bind((serverAddress,serverPort))
		serverSocket.listen(10)
		print('The server is ready to receive')
		return serverSocket
	except:
		print('Error: Server could not create socket please change port number or check connection')
		sys.exit(0)
		
def serverOps(connectionSocket,addr): # this is the thread that will start the authentication process and 
	#lists for authentication
	global socketList
	global online
	pwords = ['p000','p000','p000','p591']
	users =  ['test1','test2','test3','nvaughn']
	authUser = ''
	#receiving HELLO data to intiate interactions         
	data = connectionSocket.recv(1024).decode()
	if 'HELLO' in data:
		#sending data
		dataStr = 'HELLO\n'     
		connectionSocket.send(dataStr.encode())
	else: #ending the connection they failed to answer hello
		connectionSocket.close()
		return 
	
	count = 0
	while True: #this loop is for authenticating the user returning affirmitive or negative responses
		# client connection will close after 4 tries
		#waiting to receive user auth data          
		data = connectionSocket.recv(1024).decode()
		a,usr,pswd = data.split(':')
		if any(usr in u for u in users) and any(pswd in p for p in pwords): 
			socketList.append((usr,connectionSocket))
			dataStr = 'AUTHYES\n'
			connectionSocket.send(dataStr.encode())
			if usr not in online:
				online.append(usr)
				authUser = usr # this will be used to keep track of our user name
				signin = 'SIGNIN: ' + usr + '\n'
				for s in socketList:
					s[1].send(signin.encode())
			
			break
		elif count == 3:#disconnecting the client too many bad choices
			dataStr = 'AUTHNO\n'
			connectionSocket.send(dataStr.encode())
			connectionSocket.close()
			return
		dataStr = 'AUTHNO\n'
		connectionSocket.send(dataStr.encode())
		count = count + 1 #increment the loop	
	while True: # this loop will run the main operations of sending messages 
		data = connectionSocket.recv(1024).decode()
		if 'LIST' in data:
			olist = ', '.join(online)
			connectionSocket.send(olist.encode())
		elif 'TO:' in data:
			stat,usr,msg = data.split(':')
			sendingMsg = 'FROM:' + authUser + ':' + msg + '\n'
			for s in socketList:
				if s[0] == usr:
					s[1].send(sendingMsg.encode())
		else:
			usrCount = 0 # using this to count how many users there are with the same name
			for s in socketList:
				if s[0] == authUser:
					usrCount = usrCount + 1
			if usrCount == 1:		
				signin = 'SIGNOFF:' + authUser + '\n'
				for s in socketList:
					s[1].send(signin.encode())
				online.remove(authUser)				
			socketList.remove((authUser,connectionSocket))
			connectionSocket.close()
			return
			
			
def main():
	serverSocket = initServer()
	threads= [] #storing threads in here, in case I need to edit them in the future
	while True:
		connectionSocket, addr = serverSocket.accept()
		#code snippet inspired from https://pymotw.com/2/threading/
		t = threading.Thread(target=serverOps, args=(connectionSocket, addr))
		threads.append(t)
		t.start() 
	serverSocket.close()
	

if __name__ == "__main__":
   main()
