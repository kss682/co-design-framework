

class Mode:
    def __init__(
            self,
            mode_id,
            name:str,
            streams:list,
            schedule
            ):
        self.mode_id = mode_id
        self.name = name
        self.streams = streams
        self.schedule = schedule
    
    def __str__(self):
        return "mode_"+str(self.mode_id)

    def __rep__(self):
        return f"Mode(id={self.mode_id}, name={self.name})"