import multiprocessing
from multiprocessing import Queue
import numpy as np
from .ffmpeg_reader import FFmpegReader

NFRAME = 10

class FFmpegReaderNoblock(FFmpegReader):
    def __init__(self, 
                 vcap_fun,
                 *vcap_args, **vcap_kwargs):
        vid:FFmpegReader = vcap_fun(*vcap_args, **vcap_kwargs)
        vid.release()

        # work like normal FFmpegReaderObj
        props_name = ['width', 'height', 'fps', 'count', 'codec', 'ffmpeg_cmd',
                      'size', 'pix_fmt', 'out_numpy_shape', 'iframe']
        for name in props_name:
            setattr(self, name, getattr(vid, name, None))
        
        # 创建共享内存的NumPy数组
        shared_array = multiprocessing.Array('b', int(NFRAME*np.prod(self.out_numpy_shape)))

        # 将共享内存的NumPy数组转换为NumPy数组
        self.np_array = np.frombuffer(shared_array.get_obj(), dtype=np.uint8).reshape((NFRAME,*self.out_numpy_shape))
        
        self.shared_array = shared_array
        self.vcap_args = vcap_args
        self.vcap_kwargs = vcap_kwargs
        self.q = Queue(maxsize=NFRAME)
        self.vcap_fun = vcap_fun
        self.has_init = False

    def read(self):
        if not self.has_init:
            self.has_init = True
            process = multiprocessing.Process(target=child_process, 
                                              args=(self.shared_array, self.q, self.vcap_fun,
                                                    self.vcap_args, self.vcap_kwargs))
            process.start()
            self.process = process
        
        data_id = self.q.get()
        if data_id is None:
            return False, None
        else:
            return True, self.np_array[data_id]


def child_process(shared_array, q:Queue, vcap_fun, vcap_args, vcap_kwargs):
    vid = vcap_fun(*vcap_args, **vcap_kwargs)
    np_array = np.frombuffer(shared_array.get_obj(), dtype=np.uint8).reshape((NFRAME,*vid.out_numpy_shape))
    with vid:
        for i, img in enumerate(vid):
            iloop = i % NFRAME
            q.put(iloop)
            # 在子进程中修改共享内存的NumPy数组
            np_array[iloop] = img
        q.put(None)
