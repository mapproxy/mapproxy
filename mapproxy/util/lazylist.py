# This file is part of the MapProxy project.
# Copyright (C) 2010 Omniscale <http://omniscale.de>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
LazyList decorator and support helper function
"""


import threading
# callable does not present in Python 3.0 - 3.2
try:
    callable
except NameError:
    from collections import Callable
    callable=lambda x: isinstance(x,Callable)

'''
 Return true if y is attribute of x and y is instance of callable
'''
iscallable=lambda x,y: hasattr(x,y) and callable(getattr(x,y))

'''
 Check value of flat
'''
checkFlag=lambda src,flag: (iscallable(src,flag) and getattr(src,flag)()) or (not iscallable(src,flag) and hasattr(src,flag) and getattr(src,flag))

'''    
    Decorators installer
'''
def decorateList(decorator):
    _props = (
        '__str__', '__repr__', '__unicode__',
        '__hash__', '__sizeof__', '__cmp__', '__nonzero__',
        '__lt__', '__le__', '__eq__', '__ne__', '__gt__', '__ge__',
        'append', 'count', 'index', 'extend', 'insert', 'pop', 'remove',
        'reverse', 'sort', '__add__', '__radd__', '__iadd__', '__mul__',
        '__rmul__', '__imul__', '__contains__', '__len__', '__nonzero__',
        '__getitem__', '__setitem__', '__delitem__', '__iter__',
        '__reversed__', '__getslice__', '__setslice__', '__delslice__')
    def decorate(cls):
        for attr in _props: 
            if iscallable(cls,attr):
                setattr(cls, attr, decorator(getattr(cls, attr)))
        return cls
    return decorate
    
'''
    LazyList decorator
    Use @decorateList(lazy())
    or
    Use @decorateList(lazy(fillname="data",lockname="_lock",ready="isdataready",once="isOnce"))
'''   

def lazy(fillname='get_value',lockname='_lazy_lock',ready="ready",once="once"): 
    def _lazy(attr):
        def __lazy(self, *args, **kw):
            if not hasattr(self,lockname):
                setattr(self,lockname,threading.Lock())
            lock=getattr(self,lockname)
            if hasattr(self,fillname):
                src=getattr(self,fillname)
                if src is not None:
                    lock.acquire()
                    try:
                        if checkFlag(self,ready):
                            if callable(src):
                                listval=src()
                            else:
                                listval=src
                            if list.__len__(self)>0:
                                list.__delitem__(self,slice(0,list.__len__(self)))
                            list.extend(self,listval)
                            
                            
                            if checkFlag(self,once):
                                    delattr(self,fillname)
                    except (KeyboardInterrupt,SystemExit):
                        raise
                    except:
                        pass
                    finally:
                        lock.release()
                else:
                    delattr(self,fillname)
            return attr(self, *args, **kw)
        return __lazy
    return _lazy
    
'''    
 Return function wich check this condition: "Is the time reached"?
 Use
    timeCondition=measure(5)
    timeCondition() # return False
    time.sleep(10)
    timeCondition() # return True
    
 Full
    timeCondition=measure(5,first=True,once=False) # return True on first call whenever is interval reached
    timeCondition() # return True
    timeCondition() # return False
    time.sleep(10)
    timeCondition() # return True
    
'''
from datetime import datetime,timedelta
from numbers import Number
def measure(interval,first=False,once=False):

    next=datetime.today()
    if isinstance(interval,Number):
        interval=timedelta(seconds=interval)
    elif isinstance(interval,datetime):
        interval=interval-next
        once=True
        first=False
    elif interval is None:
        interval=timedelta(seconds=0)
        once=True
    else:
        raise TypeError("'delta' need to be one of this type: None, Number, timedelta, datatime")
    if interval<=timedelta(seconds=0):
        interval=timedelta(seconds=0)
        once=True
    if first:
        next-=interval
    param=dict([("next",next),("happend",False),("interval",interval)])

    def _check():
        if param["happend"] and once:
            return False
        current=datetime.today()
        if current-param["next"]>=interval:
            param["happend"]=True
            param["next"]=current
            return True
        return False
    
    return _check
    


