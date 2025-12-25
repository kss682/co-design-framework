

class Mode:
    def __init__(
            self,
            _id,
            _name:str,
            _streams:list,
            _schedule
            ):
        self._id = _id
        self.name = _name
        self.streams = _streams
        self.schedule = _schedule
    
    def __str__(self):
        return "mode_"+str(self._id)