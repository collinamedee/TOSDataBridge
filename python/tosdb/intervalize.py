from threading import Thread as _Thread
import tosdb
import time as _time

def _bind_class_fields_late_for_time_interval(cls):
    cls.min         = cls(60)
    cls.three_min   = cls(180)
    cls.five_min    = cls(300)
    cls.ten_min     = cls(600)
    cls.thirty_min  = cls(1800)
    cls.hour        = cls(3600)
    cls.two_hour    = cls(7200)
    cls.four_hour   = cls(14400) 
    return cls    
@_bind_class_fields_late_for_time_interval
class TimeInterval:
    def __init__(self,val):
        self.val = val

        
class _GetOnInterval:       
    def __init__(self,block,item,topic):      
        if not isinstance(block, tosdb._TOS_DataBlock):
            raise TypeError("block must be of type tosdb.TOS_DataBlock")
        self._block = block
        if topic.upper() not in block.topics():
            raise ValueError("block does not have topic: " + str(topic) )
        self._topic = topic
        if item.upper() not in block.items():
            raise ValueError("block does not have item: " + str(item) )
        self._item = item
        self._rflag = False    

class GetOnTimeInterval( _GetOnInterval ):
    def __init__(self,block,item,topic):
        _GetOnInterval.__init__(self,block,item,topic)
        if block.info()['DateTime'] == 'Disabled':
            raise ValueError("block does not have datetime enabled")

    # active_interval storage/functionality

    @classmethod
    def send_to_file( cls, block, item, topic, file_path,
                  time_interval=TimeInterval.five_min,
                  update_seconds=15, use_pre_roll_val=True ):                
        file = open(file_path,'w')
        i = cls(block,item,topic)
        file.seek(0)
        file.write(str(block.info()))
        file.write('item: ' + item + '\n')
        file.write('topic: ' + topic + '\n')
        file.write('time_interval: ' + str(time_interval.val) + '\n' )
        file.write('update_seconds: ' + str(update_seconds) + '\n' )
        file.write('use_pre_roll_val: ' + str(use_pre_roll_val) + '\n' )
        run_cb = lambda x: file.write( str(x[0]) + ' ' + str(x[1]) + '\n' )
        stop_cb = lambda : file.close()
        if cls._check_start_args( run_cb, stop_cb, time_interval,
                                  update_seconds):
            i.start( run_cb, stop_cb, time_interval, update_seconds)
        return i            
        
    @staticmethod
    def _check_start_args( run_callback, stop_callback, time_interval,
                           update_seconds):
        if not callable(run_callback) or not callable(stop_callback):                    
            raise TypeError("callback must be callable")
        if type(time_interval) is not TimeInterval:
            raise TypeError("time_interval must be of type TimeInterval")
        if divmod(time_interval.val,60)[1] != 0:
            raise ValueError("time_interval value must be divisible by 60")
        if update_seconds > (time_interval.val / 2):
            raise ValueError("update_seconds greater than half time_interval")
        return True
                 
    def start( self, run_callback, stop_callback,
               time_interval=TimeInterval.five_min, update_seconds=15 ):        
        self._check_start_args( run_callback, stop_callback, time_interval,
                                update_seconds )
        self._run_callback = run_callback
        self._stop_callback = stop_callback
        self._interval_seconds = time_interval.val        
        self._update_seconds = update_seconds
        self._rflag = True
        self._thread = _Thread( target=self._update, daemon=True )
        self._thread.start()        
        
    def stop(self):
        self._rflag = False
        self._stop_callback()

    def _update(self):
        carry = None
        while self._rflag:
            try:
                dat = self._block.stream_snapshot_from_marker( self._item,
                                                               self._topic,
                                                               True)
                if dat and len(dat) >= 1:
                    roll = self._find_last_roll( dat +
                                                 ([carry] if carry else []) )
                    if roll:
                        self._run_callback( roll )
                    carry = dat[0] # carry to the back of next snapshot
                for i in range(self._update_seconds):
                    _time.sleep( 1 )
                    if not self._rflag:
                        break
            except:
                print("error in GetOnTimeInterval._update loop")
                self.stop()
                
    def _find_last_roll(self, snapshot):
        last_item = snapshot[0]
        if self._interval_seconds <= 60:            
            for this_item in snapshot[1:]:               
                if last_item[1].min > this_item[1].min:
                    return (this_item,last_item)
                else:
                    last_item = this_item                      
        elif self._interval_seconds <= 3600:
            intrvl_min = self._interval_seconds / 60          
            for this_item in snapshot[1:]:
                last_mod = last_item[1].min % intrvl_min
                this_mod = this_item[1].min % intrvl_min
                if last_mod == 0 and this_mod != 0:
                    return (this_item,last_item)
                else:
                    last_item = this_item           
        elif self._interval_seconds <= 86400:
            intrvl_hour = self._interval_seconds / 3600            
            for this_item in snapshot[1:]:
                last_mod = last_item[1].hour % intrvl_hour
                this_mod = this_item[1].hour % intrvl_hour
                if last_mod == 0 and this_mod != 0:
                    return (this_item,last_item)
                else:
                    last_item = this_item
  
      

