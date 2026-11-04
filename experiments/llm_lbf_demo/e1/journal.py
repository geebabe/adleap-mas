"""Hash-chained, fsync-per-event journal; uncertain live requests fail closed."""
import fcntl
import json
import os
from pathlib import Path
from .common import canonical,digest


class Journal:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.handle=self.path.open('a+',encoding='utf-8')
        try:fcntl.flock(self.handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            self.handle.close();raise RuntimeError('run already locked') from None
        try:self.events=self.read(self.path)
        except Exception:
            self.close();raise
    @staticmethod
    def read(path):
        events=[];previous=None
        with Path(path).open(encoding='utf-8') as f:
            for line in f:
                if not line.endswith('\n'):raise ValueError('torn journal tail; reconcile instead of silently truncating')
                event=json.loads(line);stored=event.pop('event_hash')
                if event.get('sequence')!=len(events) or event.get('previous_hash')!=previous or digest(event)!=stored:
                    raise ValueError('journal integrity failure')
                event['event_hash']=stored;events.append(event);previous=stored
        return events
    def append(self,event):
        row={**event,'sequence':len(self.events),'previous_hash':self.events[-1]['event_hash'] if self.events else None}
        row['event_hash']=digest(row)
        self.handle.write(canonical(row)+'\n');self.handle.flush();os.fsync(self.handle.fileno())
        self.events.append(row)
        return row
    def close(self):
        if not self.handle.closed:
            fcntl.flock(self.handle,fcntl.LOCK_UN);self.handle.close()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
