##########################################################
# This RNS example demonstrates a simple filetransfer    #
# server and client program. The server will serve a     #
# directory of files, and the clients can list and       #
# download files from the server.                        #
#                                                        #
# Please note that using RNS Resources for large file    #
# transfers is not recommended, since compression,       #
# encryption and hashmap sequencing can take a long time #
# on systems with slow CPUs, which will probably result  #
# in the client timing out before the resource sender    #
# can complete preparing the resource.                   #
#                                                        #
# If you need to transfer large files, use the Bundle    #
# class instead, which will automatically slice the data #
# into chunks suitable for packing as a Resource.        #
##########################################################

import os
import sys
import time
import threading
import argparse
import RNS
import RNS.vendor.umsgpack as msgpack
import POPR
from LXMF import LXMessage

APP_NAME = "popr"
SERVER_NAME = "I DIDN'T CONFIGURE THIS CORRECTLY"

# We'll also define a default timeout, in seconds
APP_TIMEOUT = 45.0

##Commands

    #QUIT
    #STAT
    #LIST
    #RETR
    #DELE
    #NOOP
    #RSET
    #TOP
    #UIDL



##########################################################
#### Server Part #########################################
##########################################################

serve_path = None
STATE = POPR.IDLE 
MB = None

# This initialisation is executed when the users chooses
# to run as a server
def server(configpath, path):
    reticulum = RNS.Reticulum(configpath)
    server_identity = RNS.Identity()

    global serve_path
    serve_path = path
    server_destination = RNS.Destination(
        server_identity,
        RNS.Destination.IN,
        RNS.Destination.SINGLE,
        APP_NAME,
        "delivery"
    )

    server_destination.set_link_established_callback(client_connected)
    #QUIT
    server_destination.register_request_handler("QUIT",response_generator = QUIT_CALLBACK,allow = RNS.Destination.ALLOW_ALL)
    #STAT
    server_destination.register_request_handler("STAT",response_generator = STAT_CALLBACK,allow = RNS.Destination.ALLOW_ALL)
    #LIST
    server_destination.register_request_handler("LIST",response_generator = LIST_CALLBACK,allow = RNS.Destination.ALLOW_ALL)
    #RETR
    server_destination.register_request_handler("RETR",response_generator = RETR_CALLBACK,allow = RNS.Destination.ALLOW_ALL)
    #DELE
    server_destination.register_request_handler("DELE",response_generator = DELE_CALLBACK,allow = RNS.Destination.ALLOW_ALL)
    #NOOP
    server_destination.register_request_handler("NOOP",response_generator = NOOP_CALLBACK,allow = RNS.Destination.ALLOW_ALL)
    #RSET
    server_destination.register_request_handler("RSET",response_generator = RSET_CALLBACK,allow = RNS.Destination.ALLOW_ALL)
    #TOP
    #UIDL
    server_destination.register_request_handler("UIDL",response_generator = UIDL_CALLBACK,allow = RNS.Destination.ALLOW_ALL)
    
    announceLoop(server_destination)

def announceLoop(destination):
    # Let the user know that everything is ready
    RNS.log("File server "+RNS.prettyhexrep(destination.hash)+" running")
    RNS.log("Hit enter to manually send an announce (Ctrl-C to quit)")

    # We enter a loop that runs until the users exits.
    # If the user hits enter, we will announce our server
    # destination on the network, which will let clients
    # know how to create messages directed towards it.
    while True:
        entered = input()
        destination.announce()
        RNS.log("Sent announce from "+RNS.prettyhexrep(destination.hash))

# Here's a convenience function for listing all files
# in our served directory
def list_files():
    # We add all entries from the directory that are
    # actual files, and does not start with "."
    global serve_path
    return [file for file in os.listdir(serve_path) if os.path.isfile(os.path.join(serve_path, file)) and file[:1] != "."]

# When a client establishes a link to our server
# destination, this function will be called with
# a reference to the link. We then send the client
# a list of files hosted on the server.
def client_connected(link):
    RNS.log("Client connected")
    global STATE
    # Check if the served directory still exists
    if STATE != POPR.IDLE:
      data = " MAILBOX LOCKED".encode("utf-8")
      data = POPR.CTL.NEG+data
      data_packet = RNS.Packet(link, data)
      data_receipt = data_packet.send()
      link.teardown()

    else:
      global MB, serve_path
      # MM = POPR.MailMessage(None, 8675309)
      # MM.size = 123

      MB = POPR.Mailbox(serve_path)
      MB.link = link
      MB.LoadAllFromDirectory()
      # MB.Add(MM)

      # MM = POPR.MailMessage(None, 1275309)
      # MM.size = 321
      # MB.Add(MM)

      # MM = POPR.MailMessage(None, 8673409)
      # MM.size = 1465
      # MB.Add(MM)

      # MM = POPR.MailMessage(None, 8644409)
      # MM.size = 33
      # MB.Add(MM)

      # MM = POPR.MailMessage(None, 8600009)
      # MM.size = 13
      # MB.Add(MM)
      
      # data = " POPR <"+SERVER_NAME+"> GO"
      # data = data.encode("utf-8")
      # data = POPR.CTL.POS+data
      # data_packet = RNS.Packet(link, data)
      # data_receipt = data_packet.send()
      # data_receipt.set_timeout(APP_TIMEOUT)
      # data_receipt.set_delivery_callback(pre_auth)
      # data_receipt.set_timeout_callback(list_timeout)
      STATE = POPR.AUTHORIZATION
      
      
        #Check the size of the packed data
        # if len(data) <= RNS.Link.MDU:
            #If it fits in one packet, we will just
            #send it as a single packet over the link.
            # list_packet = RNS.Packet(link, data)
            # list_receipt = list_packet.send()
            # list_receipt.set_timeout(APP_TIMEOUT)
            # list_receipt.set_delivery_callback(list_delivered)
            # list_receipt.set_timeout_callback(list_timeout)
      link.set_packet_callback(client_request)
      link.set_remote_identified_callback(remote_identified)


def client_disconnected(link):
    global STATE 
    STATE = POPR.IDLE
    RNS.log("Client disconnected")

def client_request(message, packet):
    #global serve_path
    global MB
    
    command = message.decode("utf-8").split(" ")
    print("Command: ",command[0])
    command[0] = command[0].upper()
    if len(command) > 1:
      for i in range(1,len(command)):
        print("Argument: "+command[i])
        
    #QUIT
    if command[0] == "QUIT":
      #POPR.QUIT() # Should be the mailbox instance
      global STATE
      STATE = POPR.IDLE
      MB.QUIT()
      packet.link.teardown()
    #STAT
    elif command[0] == "STAT":
      data = MB.STAT()
      send_message(packet.link,data)
    #LIST
    elif command[0] == "LIST":
      buffer = ""
      if len(command) > 1:
        buffer = MB.LIST(int(command[1]))
      else:
        buffer = MB.LIST()
      if buffer != "":
        data = POPR.CTL.POS+buffer.encode("utf-8")
        send_message(packet.link,data)
      else:
        send_message(packet.link,POPR.CTL.NEG)
    #RETR
    elif command[0] == "RETR":
      if len(command)>1:
        data = MB.RETR(int(command[1]))
        send_lxm(packet.link,data)
      else:
        return CTL.NEG
    #DELE
    elif command[0] == "DELE":
      if len(command) > 1:
        buffer = MB.DELE(int(command[1]))
        #send_message(packet.link,POPR.CTL.POS)
        #MB.DELE(COMMAND[0])
        send_message(packet.link,buffer)
      else:
        send_message(packet.link,POPR.CTL.NEG)
    
    #NOOP
    elif command[0] == "NOOP":
      MB.NOOP()
      data = POPR.CTL.POS
      send_message(packet.link,data)
      
    #RSET
    elif command[0] == "RSET":
      MB.RSET()
    
    #TOP
    #UIDL - Depreciated!!
    elif command[0] == "UIDL":
      if len(command) > 1:
        data = MB.UIDL(int(command[1]))
      else:
        data = MB.UIDL()
      send_message(packet.link,data)

    #Unknown Command
    else:
      #data = "ECHO ".encode("utf-8")
      data = POPR.CTL.NEG
      send_message(packet.link,data)



##REQUESTS

    #QUIT
def QUIT_CALLBACK(path,data,request_id,link_id,remote_identity,requested_at):
      global STATE
      STATE = POPR.IDLE
      MB.QUIT()
      #link_id.teardown()
      return None
      
def STAT_CALLBACK(path,data,request_id,link_id,remote_identity,requested_at):
    #STAT
      buffer = MB.STAT()
      return buffer
      
def LIST_CALLBACK(path,data,request_id,link_id,remote_identity,requested_at):
    #LIST

      buffer = ""
      if data:
        buffer = MB.LIST(int(data))
      else:
        buffer = MB.LIST()
      if buffer != "":
        buffer = POPR.CTL.POS+buffer.encode("utf-8")
        return buffer
      else:
        return POPR.CTL.NEG
        
def RETR_CALLBACK(path,data,request_id,link_id,remote_identity,requested_at):
    #RETR
      if data:
        buffer = MB.RETR(int(data))
        send_lxm(link_id,data)
        return None
      else:
        return CTL.NEG
        
def DELE_CALLBACK(path,data,request_id,link_id,remote_identity,requested_at):
    #DELE
      if data and data > 1:
        buffer = MB.DELE(int(data))
        #send_message(packet.link,POPR.CTL.POS)
        #MB.DELE(COMMAND[0])
        return buffer
      else:
        return POPR.CTL.NEG
    
def NOOP_CALLBACK(path,data,request_id,link_id,remote_identity,requested_at):
    #NOOP
      MB.NOOP()
      return POPR.CTL.POS
      
def RSET_CALLBACK(path,data,request_id,link_id,remote_identity,requested_at):
    #RSET
      MB.RSET()
      return POPR.CTL.POS
    
    #TOP
    
def UIDL_CALLBACK(path,data,request_id,link_id,remote_identity,requested_at):
    #UIDL
      if data:
        buffer = MB.UIDL(data)
      else:
        buffer = MB.UIDL()
      return buffer

##End REQURTSTS




def send_lxm(link, message):
  if message != POPR.CTL.NEG:
    RNS.log(RNS.hexrep(message.lxm.hash))
    try:
      resource = RNS.Resource(message.lxm.packed_container(),link,callback=transfer_complete)
      resource.filename = message.hash
    except Exception as e:
      RNS.log(e)
      link.teardown()
  else:
    send_message(link,POPR.CTL.NEG)
    #try:
    #    filename = message.decode("utf-8")
    #except Exception as e:
    #    filename = None
    # if filename in list_files():
        # try:
            #If we have the requested file, we'll
            #read it and pack it as a resource
            # RNS.log("Client requested \""+filename+"\"")
            # file = open(os.path.join(serve_path, filename), "rb")
            
            # file_resource = RNS.Resource(
                # file,
                # packet.link,
                # callback=resource_sending_concluded
            # )

            # file_resource.filename = filename
        # except Exception as e:
            #If somethign went wrong, we close
            #the link
            # RNS.log("Error while reading file \""+filename+"\"", RNS.LOG_ERROR)
            # packet.link.teardown()
            # raise e
    # else:
        #If we don't have it, we close the link
        # RNS.log("Client requested an unknown file")
        # packet.link.teardown()

def transfer_complete(resource):
    if resource.status == RNS.Resource.COMPLETE:
      RNS.log("Done sending file to client")
      send_message(resource.link,POPR.CTL.POS)
    elif resource.status == RNS.Resource.FAILED:
      RNS.log("Sending file to client failed")
      send_message(resource.link,POPR.CTL.NEG)
  

# This function is called on the server when a
# resource transfer concludes.
def resource_sending_concluded(resource):
    if hasattr(resource, "filename"):
        name = resource.filename
    else:
        name = "resource"

    if resource.status == RNS.Resource.COMPLETE:
        RNS.log("Done sending \""+name+"\" to client")
    elif resource.status == RNS.Resource.FAILED:
        RNS.log("Sending \""+name+"\" to client failed")

def list_delivered(receipt):
    RNS.log("The file list was received by the client")
    
def pre_auth(receipt):
    RNS.log("Waiting for identification.")

def list_timeout(receipt):
    RNS.log("Sending list to client timed out, closing this link")
    link = receipt.destination
    link.teardown()
    
def remote_identified(link, identity):
    RNS.log("Remote identified as: "+str(identity))
    global STATE
    STATE = POPR.TRANSACTION
    send_message(link, POPR.CTL.POS+" POPR <".encode("utf-8")+SERVER_NAME.encode("utf-8")+"> GO".encode("utf-8"))
    #Ready()
    


##########################################################
#### Client Part #########################################
##########################################################

# We store a global list of files available on the server
server_files      = []

# A reference to the server link
server_link       = None

# And a reference to the current download
current_download  = None
current_filename  = None

# Variables to store download statistics
download_started  = 0
download_finished = 0
download_time     = 0
transfer_size     = 0
file_size         = 0

client_identity = None
should_quit = False


# This initialisation is executed when the users chooses
# to run as a client
def client(destination_hexhash, configpath):
    # We need a binary representation of the destination
    # hash that was entered on the command line
    try:
        dest_len = (RNS.Reticulum.TRUNCATED_HASHLENGTH//8)*2
        if len(destination_hexhash) != dest_len:
            raise ValueError(
                "Destination length is invalid, must be {hex} hexadecimal characters ({byte} bytes).".format(hex=dest_len, byte=dest_len//2)
            )
            
        destination_hash = bytes.fromhex(destination_hexhash)
    except:
        RNS.log("Invalid destination entered. Check your input!\n")
        exit()

    # We must first initialise Reticulum
    reticulum = RNS.Reticulum(configpath)
    global client_identity
    client_identity = RNS.Identity()


    # Check if we know a path to the destination
    if not RNS.Transport.has_path(destination_hash):
        RNS.log("Destination is not yet known. Requesting path and waiting for announce to arrive...")
        RNS.Transport.request_path(destination_hash)
        while not RNS.Transport.has_path(destination_hash):
            time.sleep(0.1)

    # Recall the server identity
    server_identity = RNS.Identity.recall(destination_hash)

    # Inform the user that we'll begin connecting
    RNS.log("Establishing link with server...")
    # When the server identity is known, we set
    # up a destination
    server_destination = RNS.Destination(
        server_identity,
        RNS.Destination.OUT,
        RNS.Destination.SINGLE,
        APP_NAME,
        "delivery"
    )

    # We also want to automatically prove incoming packets
    server_destination.set_proof_strategy(RNS.Destination.PROVE_ALL)
    # And create a link
    link = RNS.Link(server_destination)

    # We expect any normal data packets on the link
    # to contain a list of served files, so we set
    # a callback accordingly
    link.set_packet_callback(response_received)

    # We'll also set up functions to inform the
    # user when the link is established or closed
    link.set_link_established_callback(link_established)
    link.set_link_closed_callback(link_closed)

    # And set the link to automatically begin
    # downloading advertised resources
    link.set_resource_strategy(RNS.Link.ACCEPT_ALL)
    link.set_resource_started_callback(download_began)
    link.set_resource_concluded_callback(download_concluded)
    print("WAITING")
    global should_quit
    try:
      while not should_quit:
        time.sleep(1)
    except:
      pass
    finally:
      link.teardown()

# Requests the specified file from the server
def download(filename):
    global server_link, menu_mode, current_filename, transfer_size, download_started
    current_filename = filename
    download_started = 0
    transfer_size    = 0

    # We just create a packet containing the
    # requested filename, and send it down the
    # link. We also specify we don't need a
    # packet receipt.
    request_packet = RNS.Packet(server_link, filename.encode("utf-8"), create_receipt=False)
    request_packet.send()
    
    print("")
    print(("Requested \""+filename+"\" from server, waiting for download to begin..."))
    menu_mode = "download_started"

# This function runs a simple menu for the user
# to select which files to download, or quit
menu_mode = None
def menu():
    #global server_files, server_link
    ## Wait until we have a filelist
    #while len(server_files) == 0:
    #    time.sleep(0.1)
    #RNS.log("Ready!")
    #time.sleep(0.5)
    #while STATE != POPR.TRANSACTION:
    #  time.sleep(0.1)

    global menu_mode
    menu_mode = "main"
    should_quit = False
    while (not should_quit):
        print_menu()

        while not menu_mode == "main":
            # Wait
            time.sleep(0.25)

        user_input = input().encode("utf-8")
        send_message(server_link,user_input)
        #if user_input == "q" or user_input == "quit" or user_input == "exit":
        #    should_quit = True
        #    print("")
        # else:
            # if user_input in server_files:
                # download(user_input)
            # else:
                # try:
                    # if 0 <= int(user_input) < len(server_files):
                        # download(server_files[int(user_input)])
                # except:
                    # pass

    if should_quit:
        server_link.teardown()
        
def Ready():
  print("READY")
  Command = input()
  HandleInput(Command)
  
def HandleInput(CMD):
    command = CMD.split(" ")
    #print("Command: ",command[0])
    command[0] = command[0].upper()
    #if len(command) > 1:
    #  for i in range(1,len(command)):
    #    print("Argument: "+command[i])
    #    
    #send_command(link, CMD, DTA, ResponseCallback, FailedCallback)
    #QUIT
    if command[0] == "QUIT":
      send_command(server_link, "QUIT" , None, RequestResponse, RequestFailed)
      
    #STAT
    elif command[0] == "STAT":
      send_command(server_link, "STAT" , None, RequestResponse, RequestFailed)
      
    #LIST
    elif command[0] == "LIST":
      if len(command) > 1:
        if int(command[1]) > 0:
          send_command(server_link, "LIST" , int(command[1]), RequestResponse, RequestFailed)
        else:
          print("LIST requires a positive message number or no argument.")
          Ready()
      else:
        send_command(server_link, "LIST" , None, RequestResponse, RequestFailed)
      
        
    #RETR
    elif command[0] == "RETR":
      if len(command)>1:
        send_command(server_link, "RETR" , int(command[1]), RequestResponse, RequestFailed)
      else:
        print("RETR requires a message number.")
        
    #DELE
    elif command[0] == "DELE":
      if len(command) > 1:
        send_command(server_link, "DELE" , int(command[1]), RequestResponse, RequestFailed)
      else:
        print("DELE requires a message number.")
        Ready()
    
    #NOOP
    elif command[0] == "NOOP":
      send_command(server_link, "NOOP" , None, RequestResponse, RequestFailed)
      
    #RSET
    elif command[0] == "RSET":
      send_command(server_link, "RSET" , None, RequestResponse, RequestFailed)
    
    #TOP
    
    #UIDL
    elif command[0] == "UIDL":
      if len(command) > 1:
        try:
          argument = bytes.fromhex(command[1])
          send_command(server_link, "UIDL" , argument, RequestResponse, RequestFailed)
        except Exception as e:
          print("Exception: "+e)
          Ready()
      else:
        send_command(server_link, "UIDL" , None, RequestResponse, RequestFailed)


    #Unknown Command
    else:
      print("Unsupported command: "+command[0])
      Ready()
        
def response_received(content, packet):
    try:
      print(content.decode("utf-8"))
      Ready()
#      menu()
    except:
      pass
#    packet.link.teardown()

# This function is called when a link
# has been established with the server
def link_established(link):
    # We store a reference to the link
    # instance for later use
    global server_link
    server_link = link
    link.identify(client_identity)
    # Inform the user that the server is
    # connected
    RNS.log("Link established with server")
    RNS.log("Waiting for filelist...",RNS.LOG_INFO)

    # And set up a small job to check for
    # a potential timeout in receiving the
    # file list
    thread = threading.Thread(target=filelist_timeout_job, daemon=True)
    thread.start()

# This job just sleeps for the specified
# time, and then checks if the file list
# was received. If not, the program will
# exit.
def filelist_timeout_job():
    time.sleep(APP_TIMEOUT)

    #global server_files
    #if len(server_files) == 0:
    #    RNS.log("Timed out waiting for filelist, exiting")
    #    os._exit(0)


# When a link is closed, we'll inform the
# user, and exit the program
def link_closed(link):
    if link.teardown_reason == RNS.Link.TIMEOUT:
        RNS.log("The link timed out, exiting now")
    elif link.teardown_reason == RNS.Link.DESTINATION_CLOSED:
        RNS.log("The link was closed by the server, exiting now")
    else:
        RNS.log("Link closed, exiting now")
    
    RNS.Reticulum.exit_handler()
    time.sleep(1.5)
    os._exit(0)

# When RNS detects that the download has
# started, we'll update our menu state
# so the user can be shown a progress of
# the download.
def download_began(resource):
    global menu_mode, current_download, download_started, transfer_size, file_size
    current_download = resource
    
    if download_started == 0:
        download_started = time.time()
    
    transfer_size += resource.size
    file_size = resource.total_size
    
    menu_mode = "downloading"

# When the download concludes, successfully
# or not, we'll update our menu state and 
# inform the user about how it all went.
def download_concluded(resource):
    #global menu_mode, current_filename, download_started, download_finished, download_time
    #download_finished = time.time()
    #download_time = download_finished - download_started

    
    RNS.log("Resource")
    if resource.status == RNS.Resource.COMPLETE:
        RNS.log("Complete")
        Package = resource.data.read()
        RNS.log("Package")
        container = msgpack.unpackb(Package)
        RNS.log("Container")
        message = LXMessage.unpack_from_bytes(container["lxmf_bytes"])
        RNS.log("Unpack")
        filehash = RNS.hexrep(message.hash,delimit = "")
        RNS.log(filehash)
        
        if os.path.isfile(filehash):
            RNS.log("File already exists! Overwriting")

        try:
            message.write_to_directory(".")
        except Exception as e:
            RNS.log("File operation failed!")
            RNS.log(e)
    else:
        RNS.log("Resource terminated in a way other than complete.")

# A convenience function for printing a human-
# readable file size
def size_str(num, suffix='B'):
    units = ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']
    last_unit = 'Yi'

    if suffix == 'b':
        num *= 8
        units = ['','K','M','G','T','P','E','Z']
        last_unit = 'Y'

    for unit in units:
        if abs(num) < 1024.0:
            return "%3.2f %s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.2f %s%s" % (num, last_unit, suffix)

# A convenience function for clearing the screen
def clear_screen():
    os.system('cls' if os.name=='nt' else 'clear')
    
    
def RequestResponse(reciept):
  print(str(reciept.response.decode("utf-8")))
  Ready()

def RequestFailed(reciept):
  RNS.log("Request failed. Terminating application.")
  server_link.teardown()
 
  
##########################################################
#### General #############################################
##########################################################

def send_message(link,data):
  data_packet = RNS.Packet(link, data)
  data_receipt = data_packet.send()
  
def send_command(link, CMD, DTA, ResponseCallback, FailedCallback):
  link.request(
    CMD,
    DTA,
    ResponseCallback,
    FailedCallback
  )

##########################################################
#### Program Startup #####################################
##########################################################

# This part of the program runs at startup,
# and parses input of from the user, and then
# starts up the desired program mode.
if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(
            description="Simple file transfer server and client utility"
        )

        parser.add_argument(
            "-s",
            "--serve",
            action="store",
            metavar="dir",
            help="serve a directory of files to clients"
        )

        parser.add_argument(
            "--config",
            action="store",
            default=None,
            help="path to alternative Reticulum config directory",
            type=str
        )

        parser.add_argument(
            "destination",
            nargs="?",
            default=None,
            help="hexadecimal hash of the server destination",
            type=str
        )

        args = parser.parse_args()

        if args.config:
            configarg = args.config
        else:
            configarg = None

        if args.serve:
            if os.path.isdir(args.serve):
                server(configarg, args.serve)
            else:
                RNS.log("The specified directory does not exist")
        else:
            if (args.destination == None):
                print("")
                parser.print_help()
                print("")
            else:
                client(args.destination, configarg)

    except KeyboardInterrupt:
        print("")
        exit()