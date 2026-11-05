"""Request-scoped bus with registered specialist handlers and failure messages."""
from dataclasses import dataclass, asdict
import time

@dataclass
class Message:
    sequence:int
    sender:str
    receiver:str
    performative:str
    content:dict
    duration_ms:float=0.


class MessageBus:
    def __init__(self):
        self.handlers={}; self.messages=[]

    def register(self, name, handler):
        self.handlers[name]=handler

    def emit(self,sender,receiver,performative,content,duration_ms=0.):
        message=Message(len(self.messages)+1,sender,receiver,performative,content,round(duration_ms,3))
        self.messages.append(asdict(message))

    def request(self,sender,receiver,content,performative='REQUEST'):
        self.emit(sender,receiver,performative,content); start=time.perf_counter()
        try:
            result=self.handlers[receiver](content)
        except Exception as exc:
            self.emit(receiver,sender,'FAILURE',{'error':type(exc).__name__},(time.perf_counter()-start)*1000)
            raise
        self.emit(receiver,sender,'RESPONSE' if performative=='CHALLENGE' else 'INFORM',result,(time.perf_counter()-start)*1000)
        return result
