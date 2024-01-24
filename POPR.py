###
#
# POPR - Post Office Protocol, Reticulum
#
# Alpha testing version. Code is not in final form, but
# API should not change
#
# Client is expected to perform most logic.
###

import RNS
import CTL
import os
from LXMF import LXMessage
import LXMF
import RNS.vendor.umsgpack as msgpack

# State Enumerations
IDLE = 0
AUTHORIZATION = 1
TRANSACTION = 2
UPDATE = 3

# Main class
class Mailbox:

  # Initialization: Default mail location is in the PWD of
  # the script when called, or whatever Python views as "."
  #
  # This is probably not what's desired.
  def __init__(self,path=None):
    # Directory containing MailMessages keyed by hash.
    
    self.Messages = {}
    
    # List of message hashes to maintain a constant index.
    # This index, and the associated hashes, MUST NOT be
    # modified while the mailbox is in use. This, and the
    # numbering starting with one, is required for 
    # compliance with the POPR specification.
    
    self.Indexed = ["Undefined"]
    
    self.link = None
    self.server_lxmf_delivery = None
    self.lxm_router = None
    if path:
      RNS.log("Loading mailbox from "+str(path))
      self.path = path
    else:
      RNS.log("Path is None, defaulting to .")
      self.path = "."
      
  # Adds a MailMessage, not an LXMessage, to the directories
  def Add(self,Mess):
    self.Messages[Mess.hash] = Mess
    self.Indexed.append(Mess)
    
  # Loads all LXMF files from PATH.
  # This requires the filename be the message path,
  # which is compliant with NomadNet
  def LoadAllFromDirectory(self):
    for file in os.listdir(self.path):
      handle = os.path.join(self.path,file)
      if os.path.isfile(handle):
        try:
          self.LoadLXMFromFile(handle)
        except Exception as e:
          RNS.log("File "+str(handle)+" cannot be loaded: "+str(e))
          
  
  # Receive an LXMessage, validate it, and add it to the file system.
  # Compliant with NomadNet format, but not directory structure
  def Ingest(self,L):
    try:
      if not L.signature_validated:
        RNS.log("Reject "+RNS.hexrep(L.hash,delimit = "")+": Signature not validated")
        return
      filename = RNS.hexrep(L.hash, delimit = "")
      L.write_to_directory(self.path)
      RNS.log("Ingesting message "+RNS.hexrep(L.hash,delimit=""))
    except Exception as e:
      RNS.log("Cannot injest message.")
  
  # Returns the index of the selected hash
  def MsgIdx(self, N):
    return self.Messages[self.Indexed[N].hash]
    
  # Loads LXMessage from file, validates it, and sends it to containerization
  def LoadLXMFromFile(self,P):
    fileonly = bytes.fromhex(P.split("/")[-1])
    with open(P,"rb") as f:
      #print(f)
      L = LXMessage.unpack_from_file(f)
      if not L.signature_validated:
        RNS.log("Reject "+RNS.hexrep(L.hash,delimit = "")+": Signature not validated")
        return
      try:
        hashhex = bytes.fromhex(RNS.hexrep(L.hash,delimit = ""))
      except:
        hashhex = bytes.fromhex("0")
      if fileonly != hashhex:
        RNS.log("Reject "+str(P)+": Message hash does not match file name.")
        return
    self.AddLXM(L)
  
  # Creates a MailMessage container and adds an LXMessage to it
  def AddLXM(self, L):
    try:
      self.Add(MailMessage(L,L.hash))
      return CTL.POS
    except Exception as e:
      RNS.log(e)
      
    return CTL.NEG
  
  # Sets the mailbox to update and terminates the connection.
  # ONLY FOR A GRACEFUL QUIT - Do not update on a fail state
  def QUIT(self):
    #run update
    self._Update()
    self.link.teardown()
    RNS.log("Quit command received")
    
    
  # Finalizes the mailbox updates and actually deletes messages
  # that have been marked for deletion. ONLY FOR A GRACEFUL QUIT
  def _Update(self):
    for M in self.Messages:
      if self.Messages[M].todelete == True:
        filename = RNS.hexrep(self.Messages[M].lxm.hash,delimit="")
        handle = self.path+"/"+filename
        if os.path.isfile(handle):
          os.remove(handle)
        else:
          RNS.log("Attempted to delete "+str(handle)+", which doesn't exist.")
    
  # Command list
  # See POPR specification for details.
    
  # Lists mailbox size in messages and bytes
  def STAT(self):
    RNS.log("Stat command received")
    MN = 0
    MS = 0
    for MOI in self.Messages:
      MN = MN + 1
      MS = MS + self.Messages[MOI].size
    buffer = CTL.POS+CTL.WS+str(MN).encode("utf-8")+CTL.WS+str(MS).encode("utf-8")
    return buffer
    
  # Lists messages
  def LIST(self,MSG = -1):
    buffer = ""
    if MSG > 0:
      RNS.log("List command received, message number "+str(MSG))
      if MSG < len(self.Indexed):
        if self.MsgIdx(MSG).todelete:
          RNS.log("List command received, invalid message specified")
        else:
          buffer+=" "+str(MSG)+" "+str(self.MsgIdx(MSG).size)+"\n"
      else:
        RNS.log("List command received, invalid message specified")
    elif MSG == -1:
      RNS.log("List command received, no message specified")
      for MOI in range(1,len(self.Indexed)):
        if self.MsgIdx(MOI).todelete:
          RNS.log("List command received, invalid message specified")
        else:
          buffer+="\n"+str(MOI)+" "+str(self.MsgIdx(MOI).size)
    else:
      RNS.log("List command received, invalid message specified")
    return buffer
      
  # Retrieves message by index
  def RETR(self,MSG):
    RNS.log("Retrieve command received, message number "+str(MSG))
    if MSG > 0:
      if MSG < len(self.Indexed):
        if self.MsgIdx(MSG).todelete:
          return CTL.NEG
        else:
          return self.MsgIdx(MSG).lxm.packed_container()
      else:
        return CTL.NEG
    else:
      return CTL.NEG
    
  # Mark message for deletion
  def DELE(self,MSG):
    RNS.log("Delete command received, message number "+str(MSG))
    if MSG < 1 or MSG > len(self.Indexed):
      RNS.log("Delete command received, invalid message number")
      return CTL.NEG
    elif self.MsgIdx(MSG).todelete:
      RNS.log("Delete command received, invalid message number - already marked for deletion")
      return CTL.NEG
    else:
      self.MsgIdx(MSG).todelete = True
      print(self.MsgIdx(MSG).todelete)
      return CTL.POS
      
    
  # No Operation
  def NOOP(self):
    RNS.log("NOOP command received")
    buffer = CTL.POS
    return buffer
    
  # Reset all files marked for deletion
  def RSET(self):
    for M in self.Messages:
      self.Messages[M].todelete = False
    RNS.log("Reset command received")
    
  # List message hash(es)
  def UIDL(self,MSG = None):
    buffer = " "
    found = False
    if MSG:
      RNS.log("UIDL command received, Target Hex = "+RNS.hexrep(MSG))
      for MOI in range(1,len(self.Indexed)):
        if self.MsgIdx(MOI).hash == MSG:
          if found:
            # There should never be a duplicate!
            RNS.log("Multiple returns found!")
            buffer += "\n"
          buffer += str(MOI)+" "+RNS.hexrep(self.MsgIdx(MOI).hash,delimit = "")
          found = True
      if found:
        buffer = CTL.POS+buffer.encode("utf-8")
      else:
        buffer = CTL.NEG
      return buffer
      
    else:
      RNS.log("UIDL command received, no message specified")
      for MOI in range(1,len(self.Indexed)):
        if self.MsgIdx(MOI).todelete:
          RNS.log("UIDL command received, invalid message specified")
        else:
          buffer+="\n"+str(MOI)+" "+RNS.hexrep(self.MsgIdx(MOI).hash,delimit = "")
    return buffer.encode("utf-8")
    
  # Send message in LXMessage format
  # Cb is byte packed MessageContainer
  def SEND(self,Cb):
    if Cb == None:
      RNS.log("SEND command received - None")
    else:
      RNS.log("SEND command received")
      C=MessageContainer("0")
      C.unpack(Cb)
      print("Destination: "+C.destination)
      destination_identity = RNS.Identity.recall(bytes.fromhex(C.destination))
      if destination_identity == None:
        basetime = time.time()
        RNS.Transport.request_path(destination_bytes)
        while destination_identity == None and (time.time() - basetime) < 30:
          destination_identity = RNS.Identity.recall(destination_bytes)
          time.sleep(1)
      if destination_identity == None:
        print("Error: Cannot recall identity")
        return CTL.NEG
      lxmf_destination = RNS.Destination(
        destination_identity,
        RNS.Destination.OUT,
        RNS.Destination.SINGLE,
        "lxmf",
        "delivery"
      )
      LN = LXMF.LXMessage(
        lxmf_destination, 
        self.server_lxmf_delivery, 
        C.content,
        title = C.title,
        fields = C.fields,
        desired_method=LXMF.LXMessage.DIRECT
      )

      
      self.lxm_router.handle_outbound(LN)
    buffer = CTL.POS
    return buffer
  
# Container for storing message and metadata in the mailbox
class MailMessage:
  def __init__(self, lxm_component, message_hash):
    self.date = lxm_component.timestamp
    self.size = lxm_component.packed_size
    self.todelete = False
    self.lxm = lxm_component
    self.hash = message_hash
    
# Container for LXM data and byte (un)packing calls
class MessageContainer:
  def __init__(self, destination_hash,title=None,content=None,fields=None):
    self.title = title
    self.content = content
    self.fields = fields
    self.destination = destination_hash
    
  def pack(self):
    payload = {}
    payload["title"] = self.title
    payload["content"] = self.content
    payload["fields"] = self.fields
    payload["destination"] = self.destination
    buffer=msgpack.packb(payload)
    return buffer
    
  def unpack(self,packed):
    payload = msgpack.unpackb(packed)
    self.title = payload["title"]
    self.content = payload["content"]
    self.fields = payload["fields"]
    self.destination = payload["destination"]

    


