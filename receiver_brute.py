#-*- coding: UTF-8 -*-
# Example command: srun -n 8 python -u -m mpi4py.futures receiver_brute_mpi.py --config config.receiver.json
# this code requires the modified fluctana code, https://github.com/rmchurch/fluctana.git

import numpy as np 
import math
import adios2
import json
import argparse

import concurrent.futures
import time
import os
import socket
#import queue
#import threading
import trio

import sys
from fluctana import *

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,%(msecs)d %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)

parser = argparse.ArgumentParser(description="Receive KSTAR data using ADIOS2")
parser.add_argument('--config', type=str, help='Lists the configuration file', default='config.json')
parser.add_argument('--nompi', help='Use with nompi', action='store_true')
parser.add_argument('--debug', help='Use input file to debug', action='store_true')
## A trick to handle: python -u -m mpi4py.futures ...
idx = len(sys.argv) - sys.argv[::-1].index(__file__)
args = parser.parse_args(sys.argv[idx:])

if not args.nompi:
    from processors.readers import reader_dataman, reader_bpfile, reader_sst, reader_gen
    from mpi4py import MPI
    from mpi4py.futures import MPICommExecutor
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()
else:
    #from processors.readers_nompi import reader_dataman, reader_bpfile, reader_sst, reader_gen
    from concurrent.futures import ProcessPoolExecutor as MPICommExecutor
    comm = None
    rank = 0
    size = 1
hostname = socket.gethostname()

with open(args.config, "r") as df:
    cfg = json.load(df)
    df.close()


#TODO: Remove for non-debug
class read_stream(object):
    def __init__(self,shot,nchunk,cfg={},data_path='./'):
        self.dobj = KstarEcei(shot=shot,data_path=data_path,clist=['ECEI_L0101-2408'],verbose=False)
        self.time = self.dobj.time_base_full()
        tstarts = self.time[::nchunk]
        tstops = self.time[nchunk-1::nchunk]
        if tstarts.size>tstops.size: tstarts = tstarts[:-1]
        self.timeiter = iter(zip(tstarts,tstops))
        self.current_step = 0
        self.cfg_extra = cfg

    def get_all_data(self):
        _,data = self.dobj.get_data(trange=[self.time[0],self.time[-1]],norm=1,verbose=0)
        n = int(np.ceil(data.shape[-1]/nchunk))
        self.dataSplit = np.array_split(data,n,axis=-1)

    def get_data(self,type_str):
        if 'trange' in type_str:
            trange = next(self.timeiter)
            return trange
        else:
            #_,data = self.dobj.get_data(trange=trange,norm=1,verbose=0)
            data = self.dataSplit[self.current_step]
            self.current_step += 1
            return data

    def get_attrs(self,type_str):
        return self.cfg_extra

    def BeginStep(self):
        if (self.current_step<len(self.dataSplit)):
            return adios2.StepStatus.OK

    def CurrentStep(self):
        return self.current_step

    def EndStep(self):
        pass


def save_spec(results,tstep):
    #TODO: Determine how to use adios2 efficiently instead (and how to read in like normal, e.g. without steps?)
    #np.savez(resultspath+'delta.'+str(tstep).zfill(4)+'.npz',**results)
    with adios2.open(cfg["resultspath"]+'delta.'+str(tstep).zfill(4)+'.bp','w') as fw:
        for key in results.keys():
            fw.write(key,results[key],results[key].shape,[0]*len(results[key].shape),results[key].shape)


A = FluctAna(verbose=False)
#TODO: Modify so it can take in a cfg set
#dobjAll = KstarEcei(shot=shot,cfg=cfg,clist=['ECEI_L0101-2408'],verbose=False)
#A.Dlist.append(dobjAll)  

# Function for workers to perform, which is an analysis.
# Workers (non-master MPI workers) will process each chunk of data.
# mpi4py will be responsible for data distribution.
def perform_analysis(channel_data, cfg, tstep, trange):
    """ 
    Perform analysis
    """ 
    logging.info(f"\tWorker: do analysis: tstep = {tstep}, rank = {rank}")
    t0 = time.time()
    if(cfg["analysis"][0]["name"] == "all"):
        results = {} 
        dobjAll = KstarEcei(shot=cfg["shotnr"],cfg=cfg,clist=cfg["channel_range"],verbose=False)
        if len(A.Dlist)==0: 
            A.Dlist.append(dobjAll)
        else:
            A.Dlist[0] = dobjAll
        A.Dlist[0].data = channel_data
        A.Dlist[0].time,_,_,_,_ = A.Dlist[0].time_base(trange)
        #this could be done on rank==0 as Ralph imagined
        A.fftbins(nfft=cfg['fft_params']['nfft'],window=cfg['fft_params']['window'],
          overlap=cfg['fft_params']['overlap'],detrend=cfg['fft_params']['detrend'],full=1,scipy=True)
        results['stft'] = A.Dlist[0].spdata

        Nchannels = channel_data.shape[0] 
        for ic in range(Nchannels):
            logging.info(f"\tWorker: do analysis: tstep={tstep}, rank={rank}, analysis={ic}, hostname={hostname}")
            chstr = A.Dlist[0].clist[ic]
            done_subset = [ic]
            dtwo_subset = range(done_subset[0],Nchannels)
            #TODO: Decide on cwt, need to remove autoplot
            #1 cwt
            #A.cwt()
            #save_spec(A)
            #2 cross_power
            A.cross_power(done=0,dtwo=0, done_subset=done_subset, dtwo_subset=dtwo_subset)
            results['cross_power/'+chstr] = A.Dlist[0].val
            #3 coherence
            A.coherence(done=0,dtwo=0, done_subset=done_subset, dtwo_subset=dtwo_subset)
            results['coherence/'+chstr] = A.Dlist[0].val
            #4 cross-phase
            A.cross_phase(done=0,dtwo=0, done_subset=done_subset, dtwo_subset=dtwo_subset)
            results['cross_phase/'+chstr] = A.Dlist[0].val
            #5 correlation
            A.correlation(done=0,dtwo=0, done_subset=done_subset, dtwo_subset=dtwo_subset)
            results['correlation/'+chstr] = A.Dlist[0].val
            #6 corr_coef
            A.corr_coef(done=0,dtwo=0, done_subset=done_subset, dtwo_subset=dtwo_subset)
            results['corr_coef/'+chstr] = A.Dlist[0].val
            #7 xspec
            #TODO xspec has rnum=cnum, so have to do one at a time, decide best way
            #A.xspec(done=0,dtwo=0, done_subset=done_subset, dtwo_subset=dtwo_subset, plot=False)
            #save_spec(A)
            #8 skw
            #TODO: not same ref/cmp channel setup, check
            #A.skw(done=0,dtwo=0, done_subset=done_subset, dtwo_subset=dtwo_subset, plot=False)
            #save_spec(A)
            #9 bicoherence
            #A.bicoherence(done=0,dtwo=0, done_subset=done_subset, dtwo_subset=dtwo_subset, plot=False)
            #results['bicoherence/'+chstr] = A.Dlist[0].val
            t1 = time.time()
            # Store result in database
            # backend.store(my_analysis, analysis_result)
            logging.info(f"\tWorker: done with analysis: tstep={tstep}, rank={rank}, analysis={ic}, hostname={hostname}")
        logging.info(f"Worker: loop done: tstep={tstep}, rank={rank}, hostname={hostname}")
        save_spec(results,tstep)
        logging.info(f"perform_analysis done: tstep={tstep}, rank={rank}, hostname={hostname}")

# Function for a helper thead (dispatcher).
# The dispatcher will dispatch data in the queue (dq) and 
# distribute to other workers (non-master MPI workers) with mpi4py's MPICommExecutor.
def dispatch():
    while True:
        channel_data, cfg, tstep, trange = dq.get()
        logging.info(f"\tDispatcher: read data: tstep = {tstep}, rank = {rank}")
        if channel_data is None:
            break
        future = executor.submit(perform_analysis, channel_data, cfg, tstep, trange)
        dq.task_done()

async def consumer(receive_channel):
    async with receive_channel:
        async for (executor,channel_data, cfg, tstep, trange) in receive_channel:
            logging.info(f"\tDispatcher: read data: tstep = {tstep}, rank = {rank}")
            if channel_data is None:
                break
            future = executor.submit(perform_analysis, channel_data, cfg, tstep, trange)

# Main
async def producer(send_channel):
    #RMC Not sure if order of "withs" matter here or not
    async with send_channel:
        with MPICommExecutor(comm, root=0) as executor:
            if executor is not None:
                # Only master will execute the following block
                # Use of "__main__" is critical

                # The master thread will keep reading data, while 
                # a helper thread (dispatcher) will dispatch jobs in the queue (dq) asynchronously 
                # and distribute jobs to other workers.
                # The main idea is not to slow down the master.
                # dq = queue.Queue()
                # dispatcher = threading.Thread(target=dispatch)
                # dispatcher.start()

                # Only the master thread will open a data stream.
                # General reader: engine type and params can be changed with the config file
                if not args.debug:
                    reader.Open()
                else:
                    reader.get_all_data()

                # Main loop is here
                # Reading data (from KSTAR) and save in the queue (dq) as soon as possible.
                # Dispatcher (a helper thread) will asynchronously fetch data in the queue and distribute to other workers.
                cfg_update = False
                logging.info(f"Start data reading loop")
                tstart = time.time()
                while(True):
                    stepStatus = reader.BeginStep()
                    if stepStatus == adios2.StepStatus.OK:
                        currentStep = reader.CurrentStep()
                        logging.info(f"Step {currentStep} started")
                        trange = list(reader.get_data("trange"))
                        channel_data = reader.get_data("floats")
                        if not cfg_update:
                            cfg.update(reader.get_attrs("cfg"))
                            cfg_update = True
                        reader.EndStep()
                    else:
                        logging.info(f"Receiver: end of stream, rank = {rank}")
                        break

                    # Recover channel data 
                    #TODO: Does the generator.py have to send data over like this?
                    # channel_data = channel_data.reshape((num_channels, channel_data.size // num_channels))
                    logging.info(f"Receiver: received data tstep={currentStep}, rank = {rank}")

                    # Save data in a queue then go back to work
                    # Dispatcher (a helper thread) will fetch asynchronously.
                    await send_channel.send((executor,channel_data, cfg, currentStep, trange))
                    #dq.put((channel_data, cfg, currentStep, trange))
                logging.info(f"All data read and dispatched, time elapsed: {time.time()-tstart}")
                
                ## Clean up
                # dq.join()
                # dq.put((None, None, -1, -1))
                # dispatcher.join()
        if rank==0: logging.info(f"Receiver: done")


async def main():
    async with trio.open_nursery() as nursery:
        #create memory channel that acts as Queue (but thread-safe, not blocking)
        #set  max buffer size to math.inf, ensure all data chunks put into "queue"
        send_channel, receive_channel = trio.open_memory_channel(math.inf)
        nursery.start_soon(producer, send_channel)
        nursery.start_soon(consumer, receive_channel)


if __name__ == "__main__":

    if args.debug:
        shot = 18431; nchunk=10000
        #merge into cfg dict
        reader = read_stream(shot=shot,nchunk=nchunk,data_path=cfg["datapath"])
        reader.cfg_extra = {'shot':shot,'nfft':1000,'window':'hann','overlap':0.0,'detrend':1, 
                'TriggerTime':reader.dobj.tt,'SampleRate':[reader.dobj.fs/1e3], 
                'TFcurrent':reader.dobj.itf/1e3,'Mode':reader.dobj.mode, 
                'LoFreq':reader.dobj.lo,'LensFocus':reader.dobj.sf,'LensZoom':reader.dobj.sz}

    else:
        reader = reader_gen(cfg["shotnr"], 0, cfg["engine"], cfg["params"])
 
    trio.run(main)
