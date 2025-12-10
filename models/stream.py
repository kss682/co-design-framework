""""
    Docs
"""

class Stream:
    """
    Docstring for Message
    """

    def __init__(
        self,
        _id,
        _src,
        _dst,
        _release_time,
        _period,
        _deadline
        ):
        self._id = _id
        self.src = _src
        self.dst = _dst
        self.release_time = _release_time
        self.period = _period
        self.deadline = _deadline
