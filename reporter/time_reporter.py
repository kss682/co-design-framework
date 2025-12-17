from simpn.reporters import Reporter

class TimesReporter(Reporter):

    def __init__(self):
        self.release_time = dict()
        self.complete_time = dict()
        self.end_to_end = dict()

    def callback(self, timed_binding):
        (binding, time, event) = timed_binding
        c_id = binding[0][1].value
        if "generate" in event.get_id():
            self.release_time[c_id] = time
        if event.get_id() == "to_done":
            self.complete_time[c_id] = time
    
    def validate(self):
        for item in self.complete_time.keys():
            if self.release_time.get(item, None) is not None:
                self.end_to_end[item] = self.complete_time[item] - self.release_time[item]

        print("key | release_time | complete_time | e2e")
        for key in self.end_to_end.keys():
            print(key, "|", self.release_time[key], "|", self.complete_time[key], "|", self.end_to_end[key])
