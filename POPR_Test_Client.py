##########################################################
# Post Office Protocol, Reticulum test implementation    #
#                                                        #
# Client implementation for POPR. Designed to            #
# specification to show how the POPR module is meant     #
# to be used.                                            #
#                                                        #
# See specification for futher information.              #
#                                                        #
# Basic testing and security checks have been performed, #
# however there has been no thorough testing and this    #
# example IS NOT FOR PRODUCTION USE.                     #
#                                                        #
# This owes heavily to the RNS Resource example, and is  #
# licensed under a similar MIT licence.                  #
#                                                        #
# This code has not been cleaned or refactored. Sorry    #
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
import LXMF
import configparser

APP_NAME = "popr"


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


# A reference to the server link
server_link       = None

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
    
    # Load/create identity
    userdir = os.path.expanduser("~")
    configdir = userdir+"/.poprtestclient"
    identitypath = configdir+"/storage/identity"
    os.makedirs(configdir+"/storage",exist_ok=True) #Fails gracefully if dir exists
    if os.path.exists(identitypath):
      client_identity = RNS.Identity.from_file(identitypath)
      print("Loading identity")
    else:
      print("Making new identity")
      client_identity = RNS.Identity()
      client_identity.to_file(identitypath)
    

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
    # This may not actually be required for POPR - Legacy code
    server_destination.set_proof_strategy(RNS.Destination.PROVE_ALL)
    
    # Link callback setup
    link = RNS.Link(server_destination)
    link.set_packet_callback(response_received)
    link.set_link_established_callback(link_established)
    link.set_link_closed_callback(link_closed)

    # Core loop
    print("WAITING")
    global should_quit
    try:
      while not should_quit:
        time.sleep(1)
    except:
      pass
    finally:
      # This probably needs error handling for link == None
      link.teardown()


# Callback to only accept input when in a ready state
def Ready():
  print("READY")
  Command = input()
  HandleInput(Command)
  
# Parses string input for testing purposes. For Machine to Machine
# communicatins, this should be replaced with whatever the UI demands,
# calling the requests directly or through a wrapper like send_command
def HandleInput(CMD):
    command = CMD.split(" ")
    command[0] = command[0].upper()

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
        send_command(server_link, "RETR" , int(command[1]), RetrieveResponse, RequestFailed)
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
        
    #SEND 
    # SEND command is dummied out in test implementation. By sending a "TEST"
    # argument in position 1 will send a test message to the address in 
    # postion 2, but this is mostly designed as an example on how to use 
    # the command, and is not meant to be functional.
    
    elif command[0] == "SEND":
      if len(command) > 2:
        if command[1] == "TEST":
          # For real-world use, generate a POPR.MessageContainer
          message = POPR.MessageContainer(command[2],title = "POPR Test Message", content = "Message has been sent successfully", fields = None)
          # Then pack it to bytes
          message = message.pack()
          # And send it
          send_command(server_link,"SEND",message,RequestResponse, None)
      else:
       send_command(server_link,"SEND", None, RequestResponse, None)
      
    #Unknown Command
    else:
      print("Unsupported command: "+command[0])
      Ready()
        
        
# Callback when a response is received. Simply prints the human-readable
# packet data and sets the input back to ready.
def response_received(content, packet):
    try:
      print(content.decode("utf-8"))
      Ready()
    except:
      pass


# This function is called when a link
# has been established with the server
def link_established(link):
    global server_link
    server_link = link
    link.identify(client_identity)
    RNS.log("Link established with server")


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


# Callback when a response is received. Simply prints the human-readable
# packet data and sets the input back to ready.
def RequestResponse(receipt):
  print(str(receipt.response.decode("utf-8")))
  Ready()
  
  
# Callback to handle the results of RETR request. It attempts to decode the
# LXMessage and save it. If the decode fails, it prints the response.
def RetrieveResponse(receipt):
  L = msgpack.unpackb(receipt.response)
  try:
    L = LXMessage.unpack_from_bytes(L['lxmf_bytes'])
  except:
    pass
  if type(L) is LXMF.LXMessage:
        filehash = RNS.hexrep(L.hash,delimit = "")
        RNS.log(filehash)
        if os.path.isfile(filehash):
            RNS.log("File already exists! Overwriting")
        try:
            L.write_to_directory(".")
        except Exception as e:
            RNS.log("File operation failed!")
            RNS.log(e)
  else:
    print(str(receipt.response.decode("utf-8")))
  Ready()

def RequestFailed(receipt):
  RNS.log("Request failed.")

 
  
##########################################################
#### General #############################################
##########################################################

# Send a packet of data over the link
def send_message(link,data):
  data_packet = RNS.Packet(link, data)
  data_receipt = data_packet.send()
  
# Send a request over the link. Why not just call directly?
# Blame old me, I don't know.
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

if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(
            description="Testbed POPR Client"
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


        if (args.destination == None):
            print("")
            parser.print_help()
            print("")
        else:
            client(args.destination, configarg)

    except KeyboardInterrupt:
        print("")
        exit()