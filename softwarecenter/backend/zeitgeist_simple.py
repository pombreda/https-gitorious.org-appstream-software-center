import sys
from zeitgeist.client import ZeitgeistClient, ZeitgeistDBusInterface
from zeitgeist.datamodel import Event, ResultType, Interpretation, TimeRange, Subject

CLIENT = ZeitgeistClient()

class ZeitgeistWrapper():
    def __init__(self):
        pass
        
    def get_usage_counter(self, application, callback):
        application = "application://"+application.split("/")[-1]
        def _callback(event_ids):
            callback(len(event_ids))
        e = Event()
        e.actor = application
        CLIENT.find_event_ids_for_templates([e], _callback, 
                                                num_events = 0)
        
zeitgeist = ZeitgeistWrapper()



