##########################################################
# Post Office Protocol, Reticulum test implementation    #
#                                                        #
# Server implementation for POPR. Designed to            #
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
configdir = ""
lxmf_destination = None
lxm_router = None
current_user = None
last_action_time = None
last_announce_time = None

config = None

# configparser based configuration container. Deviates
# from usual Reticulum config parsing just because
# I was familiar with configparser and wanted speed.
class ConfigContainer:
  def __init__(self,path):
    
    # Load or create as required
    if os.path.isfile(path):
      self.Load(path)
    else:
      self.Create(path)
      
  # Loads a configuration file, then populates an object
  # to prevent repeated string lookups
  def Load(self, path):
    C = configparser.ConfigParser()
    C.read(path)
    buffer = C['MAILBOX']['ALLOWED'].split(',')
    listbuffer = []
    for S in buffer:
      listbuffer.append(bytes.fromhex(S))
    #print(listbuffer)
    self.ALLOWED = listbuffer
    self.SERVER_NAME = C['MAILBOX']['SERVER_NAME']
    self.MAILUSER_NAME = C['MAILBOX']['MAILUSER_NAME']
    self.SESSION_TIMEOUT = int(C['MAILBOX']['SESSION_TIMEOUT'])
    self.ANNOUNCE_RATE = int(C['MAILBOX']['ANNOUNCE_RATE'])
    self.PATH = C['PATHS']['MAIN']
    
  # Creates a default configuration file, then loads it.
  def Create(self, path):
    C = configparser.ConfigParser()
    C['MAILBOX'] = {}
    C['MAILBOX']['ALLOWED'] = ""
    C['MAILBOX']['SERVER_NAME'] = "I DIDN'T CONFIGURE THIS CORRECTLY"
    C['MAILBOX']['MAILUSER_NAME'] = "Unconfigured test POPR"
    C['MAILBOX']['SESSION_TIMEOUT'] = "600"
    C['MAILBOX']['ANNOUNCE_RATE'] = "43200"
    C['PATHS'] = {}
    userdir = os.path.expanduser("~")
    C['PATHS']['MAIN'] = userdir + "/.popr"
    with open(path,'w') as f:
      C.write(f)
    self.Load(path)
    

# This initialisation is executed when the users chooses
# to run as a server
def server(configpath,path):
  global configdir, lxmf_destination, lxm_router, serve_path, config, MB
  
  # Define config path, might want to migrate to file
  if path == None:
    path = os.path.expanduser("~")+"/.popr"
  config = ConfigContainer(path+"/config")
  reticulum = RNS.Reticulum(configpath)
  # Load path from configuration
  configdir = config.PATH
  identitypath = configdir+"/storage/identity"
  os.makedirs(configdir+"/storage/messages",exist_ok=True) # Fails gracefully
  os.makedirs(configdir+"/lxmrouter",exist_ok=True) # can be used as a failsafe
  if os.path.exists(identitypath):
    server_identity = RNS.Identity.from_file(identitypath)
    print("Loading identity")
  else:
    print("Making new identity")
    server_identity = RNS.Identity()
    server_identity.to_file(identitypath)
    
  
  # Path with message storage. This is where you can change your location
  # or where you want to begin to make a NomadNet by-message or 
  # recursive message store.
  serve_path = configdir+"/storage/messages"
  server_destination = RNS.Destination(
      server_identity,
      RNS.Destination.IN,
      RNS.Destination.SINGLE,
      APP_NAME,
      "delivery"
  )

  # Configure LXMRouter
  lxm_router = LXMF.LXMRouter(identity = server_identity, storagepath = configdir+"/lxmrouter")
  lxmf_destination = lxm_router.register_delivery_identity(server_identity,display_name=config.MAILUSER_NAME)
  lxm_router.register_delivery_callback(LXMReceived)
  lxmf_destination.announce()
  
  # Initialize mailbox - Initial stage
  MB = POPR.Mailbox(serve_path)
  MB.server_lxmf_delivery = lxmf_destination
  MB.lxm_router = lxm_router
  

  # Define callbacks for link and requests. 
  # This is the core conrol logic.
  server_destination.set_link_established_callback(client_connected)
  #QUIT
  server_destination.register_request_handler("QUIT",response_generator = QUIT_CALLBACK,allow = RNS.Destination.ALLOW_ALL)
  #STAT
  server_destination.register_request_handler("STAT",response_generator = STAT_CALLBACK,allow = RNS.Destination.ALLOW_LIST,allowed_list = config.ALLOWED)
  #LIST
  server_destination.register_request_handler("LIST",response_generator = LIST_CALLBACK,allow = RNS.Destination.ALLOW_LIST,allowed_list = config.ALLOWED)
  #RETR
  server_destination.register_request_handler("RETR",response_generator = RETR_CALLBACK,allow = RNS.Destination.ALLOW_LIST,allowed_list = config.ALLOWED)
  #DELE
  server_destination.register_request_handler("DELE",response_generator = DELE_CALLBACK,allow = RNS.Destination.ALLOW_LIST,allowed_list = config.ALLOWED)
  #NOOP
  server_destination.register_request_handler("NOOP",response_generator = NOOP_CALLBACK,allow = RNS.Destination.ALLOW_LIST,allowed_list = config.ALLOWED)
  #RSET
  server_destination.register_request_handler("RSET",response_generator = RSET_CALLBACK,allow = RNS.Destination.ALLOW_LIST,allowed_list = config.ALLOWED)
  #TOP
  #UIDL
  server_destination.register_request_handler("UIDL",response_generator = UIDL_CALLBACK,allow = RNS.Destination.ALLOW_LIST,allowed_list = config.ALLOWED)
  #SEND
  server_destination.register_request_handler("SEND",response_generator = SEND_CALLBACK,allow = RNS.Destination.ALLOW_LIST,allowed_list = config.ALLOWED)
  
  # Begin operational loop
  announceLoop(server_destination)

# Main loop
def announceLoop(destination):
    # Let the user know that everything is ready
    RNS.log("POPR server "+RNS.prettyhexrep(destination.hash)+" running")
    RNS.log("Hit enter to manually send an announce (Ctrl-C to quit)")
    global last_action_time, last_announce_time, MB, config, STATE
    while True:
      current_time = time.time()
      # Check if the user has timed out
      if last_action_time: # No user, no timeout
        if current_time > (last_action_time+config.SESSION_TIMEOUT):
          if MB:
            MB.link.teardown()
            MB = None
          current_user = None
          STATE = POPR.IDLE
          last_action_time = None
      # Check if we should announce
      if last_announce_time:
        if current_time > (last_announce_time+config.ANNOUNCE_RATE):
          last_announce_time = current_time
          destination.announce()
          RNS.log("Sent announce from "+RNS.prettyhexrep(destination.hash))
      else: # No last announce, so we should announce now.
        destination.announce()
        last_announce_time = current_time
        RNS.log("Sent announce from "+RNS.prettyhexrep(destination.hash))
      #Timeout/announce error <= 4 sec. Tradeoff for reducing cycles
      time.sleep(5) 
    
# When a link is established, set the callback for identification
# Don't accept any other communication until identified
def client_connected(link):
    RNS.log("Client connected")
    link.set_remote_identified_callback(remote_identified)

# On disconnect - all steps are critical
def client_disconnected(link):
    global STATE, MB
    # Return to idle state
    STATE = POPR.IDLE
    # Remove link from mailbox
    MB.link = None
    RNS.log("Client disconnected")

# Callback for LXMF ingestion
def LXMReceived(L):
  global serve_path
  # Initialize a temporary mailbox to save the data
  # regardless of current user state
  LetterBox = POPR.Mailbox(serve_path)
  LetterBox.Ingest(L)



# Request callbacks - The heart of the server logic

    #QUIT
def QUIT_CALLBACK(path,data,request_id,link_id,remote_identity,requested_at):
      unlock_mailbox() 
      MB.QUIT()
      return None
      
def STAT_CALLBACK(path,data,request_id,link_id,remote_identity,requested_at):
    #STAT
      if not verify_state(remote_identity):
        return POPR.CTL.NEG
      buffer = MB.STAT()
      return buffer
      
def LIST_CALLBACK(path,data,request_id,link_id,remote_identity,requested_at):
    #LIST
      if not verify_state(remote_identity):
        return POPR.CTL.NEG
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
      if not verify_state(remote_identity):
        return POPR.CTL.NEG
      if data:
        buffer = MB.RETR(int(data))
        return buffer
      else:
        return CTL.NEG
        
def DELE_CALLBACK(path,data,request_id,link_id,remote_identity,requested_at):
    #DELE
      if not verify_state(remote_identity):
        return POPR.CTL.NEG
      if data and data > 0:
        buffer = MB.DELE(int(data))
        return buffer
      else:
        return POPR.CTL.NEG
    
def NOOP_CALLBACK(path,data,request_id,link_id,remote_identity,requested_at):
    #NOOP
      if not verify_state(remote_identity):
        return POPR.CTL.NEG
      MB.NOOP()
      return POPR.CTL.POS
      
def RSET_CALLBACK(path,data,request_id,link_id,remote_identity,requested_at):
    #RSET
      if not verify_state(remote_identity):
        return POPR.NEG
      MB.RSET()
      return POPR.CTL.POS
    
    #TOP
    
def UIDL_CALLBACK(path,data,request_id,link_id,remote_identity,requested_at):
    #UIDL
      if not verify_state(remote_identity):
        return POPR.CTL.NEG
      if data:
        buffer = MB.UIDL(data)
      else:
        buffer = MB.UIDL()
      return buffer
      
def SEND_CALLBACK(path,data,request_id,link_id,remote_identity,requested_at):
    #SEND
      if not verify_state(remote_identity):
        return POPR.CTL.NEG
      if data:
        buffer = MB.SEND(data)
      else:
        return POPR.CTL.NEG
      return buffer


# Multi purpose function:
# Ensures that the user making the request is the current user
# of the mailbox and that the server is in the proper TRANSACTION
# state, and then resets the timeout counter
def verify_state(id):
  global current_user, STATE, last_action_time
  if id.hash != current_user:
    return False
  if STATE != POPR.TRANSACTION:
    return False
  last_action_time = time.time()
  return True

# Returns server to idle state with no logged-in user
def unlock_mailbox():
  global current_user, STATE
  STATE = POPR.IDLE
  current_user = None
  
    

# Initializes server and mailbox on valid identification
def remote_identified(link, identity):
    RNS.log("Remote identified as: "+RNS.hexrep(identity.hash,delimit=""))
    global MB, STATE, config, current_user, last_action_time
    
    # If the user is authorized:
    if identity.hash in config.ALLOWED:
      if identity.hash == current_user: # Stuck session? Restart session w/o update
        RNS.log("Client already has an open session. Terminating.")
        MB.link.teardown()
        time.sleep(2)
      elif current_user != None: # Mailbox locked. Reject
        send_message(link, POPR.CTL.NEG+" MAILBOX LOCKED".encode("utf-8"))
        time.sleep(2)
        link.teardown()
        return
      STATE = POPR.TRANSACTION
      send_message(link, POPR.CTL.POS+" POPR <".encode("utf-8")+config.SERVER_NAME.encode("utf-8")+"> GO".encode("utf-8"))
      current_user = identity.hash
      MB.link = link
      MB.LoadAllFromDirectory()
      last_action_time = time.time()
      return
      
    # If the user is unauthotized, close the link.
    send_message(link, POPR.CTL.NEG+" YOU ARE NOT AUTHORIZED TO ACCESS THIS SYSTEM".encode("utf-8"))
    time.sleep(2)
    link.teardown()
    
    #Ready()
    

  
##########################################################
#### General #############################################
##########################################################

# Send bytes over link
def send_message(link,data):
  data_packet = RNS.Packet(link, data)
  data_receipt = data_packet.send()
  

##########################################################
#### Program Startup #####################################
##########################################################

# This part of the program runs at startup,
# and parses input of from the user, and then
# starts up the desired program mode.
if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(
            description="Testbed POPR Server"
        )

        parser.add_argument(
            "server_config",
            nargs="?",
            action="store",
            metavar="dir",
            default = None,
            help="configuration directory"
        )

        parser.add_argument(
            "--config",
            action="store",
            default=None,
            help="path to alternative Reticulum config directory",
            type=str
        )


        args = parser.parse_args()

        if args.config:
            configarg = args.config
        else:
            configarg = None



        server(configarg, args.server_config)


    except KeyboardInterrupt:
        print("")
        exit()