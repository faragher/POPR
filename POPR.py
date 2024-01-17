###
#
# POPR - Post Office Protocol, Reticulum
#
# 
#
#
#
###

import RNS
import CTL
import os
from LXMF import LXMessage
import LXMF
import RNS.vendor.umsgpack as msgpack


IDLE = 0
AUTHORIZATION = 1
TRANSACTION = 2
UPDATE = 3

class Mailbox:

  def __init__(self,path=None):
    self.Messages = {}
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
      
  def Add(self,Mess):
    self.Messages[Mess.hash] = Mess
    self.Indexed.append(Mess)
    
  def LoadAllFromDirectory(self):
    for file in os.listdir(self.path):
      handle = os.path.join(self.path,file)
      if os.path.isfile(handle):
        try:
          self.LoadLXMFromFile(handle)
        except Exception as e:
          RNS.log("File "+str(handle)+" cannot be loaded: "+str(e))
          
  
    
  def Ingest(self,L):
    print("In POPR")
    try:
      if not L.signature_validated:
        RNS.log("Reject "+RNS.hexrep(L.hash,delimit = "")+": Signature not validated")
        return
      filename = RNS.hexrep(L.hash, delimit = "")
      L.write_to_directory(self.path)
      RNS.log("Ingesting message "+RNS.hexrep(L.hash,delimit=""))
    except Exception as e:
      RNS.log("Cannot injest message.")
  
  def MsgIdx(self, N):
    return self.Messages[self.Indexed[N].hash]
    
    
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
  
  def AddLXM(self, L):
    try:
      #print("This should work in general")
      #RNS.log(RNS.hexrep(L.hash))
      self.Add(MailMessage(L,L.hash))
      return CTL.POS
    except Exception as e:
      RNS.log(e)
      
    return CTL.NEG
  
  # ONLY FOR A GRACEFUL QUIT
  def QUIT(self):
    #run update
    self._Update()
    self.link.teardown()
    RNS.log("Quit command received")
    
  def _Update(self):
    for M in self.Messages:
      if self.Messages[M].todelete == True:
        filename = RNS.hexrep(self.Messages[M].lxm.hash,delimit="")
        #print("I should be deleting "+filename)
        handle = self.path+"/"+filename
        if os.path.isfile(handle):
          os.remove(handle)
        else:
          RNS.log("Attempted to delete "+str(handle)+", which doesn't exist.")
    
  def STAT(self):
    RNS.log("Stat command received")
    MN = 0
    MS = 0
    for MOI in self.Messages:
      MN = MN + 1
      MS = MS + self.Messages[MOI].size
    buffer = CTL.POS+CTL.WS+str(MN).encode("utf-8")+CTL.WS+str(MS).encode("utf-8")
    return buffer
    
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
    
  def DELE(self,MSG):
    #GO = "+OK Marked for deletion"
    #NOGO = "-ERR"
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
      
    
      
  def NOOP(self):
    RNS.log("NOOP command received")
    buffer = CTL.POS
    return buffer
    
  def RSET(self):
    for M in self.Messages:
      self.Messages[M].todelete = False
    RNS.log("Reset command received")
    

  def UIDL(self,MSG = None):
    buffer = " "
    found = False
    if MSG:
      RNS.log("UIDL command received, Target Hex = "+RNS.hexrep(MSG))
      for MOI in range(1,len(self.Indexed)):
        #RNS.log(self.MsgIdx(MOI).hash)
        if self.MsgIdx(MOI).hash == MSG:
          if found:
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
    #else:
    #  RNS.log("UIDL command received, invalid message specified")
    return buffer.encode("utf-8")
    
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
  

class MailMessage:

  def __init__(self, lxm_component, message_hash):
    #self.lxm = None
  #self.hash = None
    self.date = lxm_component.timestamp
    self.size = lxm_component.packed_size
    self.todelete = False
    self.lxm = lxm_component
    self.hash = message_hash
    
class MessageContainer:
  def __init__(self, destination_hash,title=None,content=None,fields=None):
    #self.lxm = lxm_component
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
    #buffer["payload"]=msgpack.packb(payload)
    buffer=msgpack.packb(payload)
    return buffer
    
  def unpack(self,packed):
    #payload = msgpack.unpackb(packed)["payload"]
    payload = msgpack.unpackb(packed)
    self.title = payload["title"]
    self.content = payload["content"]
    self.fields = payload["fields"]
    self.destination = payload["destination"]

    


