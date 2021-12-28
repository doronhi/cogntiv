from multiprocessing import Process
import threading
import time
import socket
import random
import sys
import numpy as np
import pickle

class Sender:
    def __init__(self, time_to_run, is_noisy, send_rate_hz = 1000):
        self.time_to_run = time_to_run
        self.send_rate_hz = send_rate_hz
        self.time_interval = 1/send_rate_hz
        self.timer = None
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.is_noisy_mode = is_noisy
        self.is_running = True
        if is_noisy:
            self.time_to_skip = time.time()
            self.update_next_time_to_skip()
        self.counter = 0
        
    def update_next_time_to_skip(self):
        delay = random.randint(2*self.send_rate_hz, 3*self.send_rate_hz)
        self.time_to_skip += (delay / self.send_rate_hz)

    def sendMessage(self):
        self.counter += 1
        if (self.is_noisy_mode and time.time() > self.time_to_skip):
            self.update_next_time_to_skip()
        else:
            data = (self.counter, np.random.normal(size=50))
            self.socket.sendto(pickle.dumps(data), ("127.0.0.1", 9090))

        self.is_running &= (time.time() < self.end_time)

        if self.is_running:
            self.next_time += self.time_interval
            self.timer = threading.Timer(self.next_time - time.time(), self.sendMessage)
            self.timer.start()

    def run(self):
        self.end_time = time.time() + self.time_to_run
        self.next_time = time.time() + self.time_interval
        self.timer = threading.Timer(self.next_time - time.time(), self.sendMessage)
        self.timer.start()
    
    def stop(self):
        if (self.timer):
            self.timer.cancel()
            self.socket.close()


class Receiver:
    def __init__(self, output_filename, rate_window_size =1):
        self.is_running = True
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.rate_counter = 0
        self.data_counter = 0
        self.rate_window_size = rate_window_size   # seconds
        self.timer = None
        self.rates = []
        self.previous_received_counter = 0
        self.data = None
        self.data_history_size = 100
        self.fout_filename = output_filename
        float_formatter = "{:.2f}".format
        np.set_printoptions(formatter={'float_kind':float_formatter})
        np.set_printoptions(linewidth=np.inf)


    def calcRate(self):
        rate = self.rate_counter / self.rate_window_size
        self.rate_counter = 0
        self.rates.append(rate)
        print ('rate:', rate)
        self.next_time += self.rate_window_size

    def run(self):
        try:
            self.fout = open(self.fout_filename, 'w')
        except OSError as err:
            print("OS error: {0}".format(err))
            return False
        self.socket.bind(("127.0.0.1",9090))
        self.socket.settimeout(1.0)
        self.next_time = time.time() + self.rate_window_size
        while self.is_running:
            if time.time() > self.next_time:
                self.calcRate()
            try:
                bytesAddressPair = self.socket.recvfrom(10000)
                full_data = pickle.loads(bytesAddressPair[0]) 
                received_counter = full_data[0]
                if (received_counter != self.previous_received_counter + 1):
                    print ('WARNING: Missed a package.')
                self.previous_received_counter = received_counter
                self.rate_counter += 1

                data = full_data[1]
                if self.data is None:
                    self.data = np.zeros([self.data_history_size, len(data)])
                self.data[self.data_counter,:] = data
                self.data_counter += 1
                if self.data_counter == self.data_history_size:
                    self.data_counter = 0
                    self.fout.write('Mean:\n')
                    self.fout.write(str(self.data.mean(0)) + '\n')
                    self.fout.write('Std:\n')
                    self.fout.write(str(self.data.std(0)) + '\n')

            except socket.timeout:
                print ('Sender is not sending.')
                self.is_running = False

        self.socket.close()

        # print statistics:
        rates = np.array(self.rates)
        print ('mean(rates)=', rates.mean())
        print ('std(rates)=', rates.std())
        self.fout.write('\n' * 3)
        self.fout.write('mean(rates)=' + str(rates.mean()) + '\n')
        self.fout.write('std(rates)=' + str(rates.std()) + '\n')
        self.fout.close()
 

def main():
    if len(sys.argv) < 2 or '--help' in sys.argv or '-h' in sys.argv:
        print ('USAGE:')
        print ('------')
        print ('com_sim.py output_filename [Options]')
        print ('--noisy        : set "noisy mode" to true')
        print ('--rate <messages_per_second> : set the messages rate - number of messages per second.')
        print ('--duration <seconds> : running duration of the program.')
        print
        return 0
    
    output_filename = sys.argv[1]
    is_noisy_mode = ('--noisy' in sys.argv)
    send_rate_hz = 1000
    duration_seconds = 4
    for idx in range(len(sys.argv)):
        if sys.argv[idx] == '--rate':
            send_rate_hz = int(sys.argv[idx+1])
        if sys.argv[idx] == '--duration':
            duration_seconds = int(sys.argv[idx+1])



    sender = Sender(duration_seconds, is_noisy_mode, send_rate_hz)
    receiver = Receiver(output_filename)
    p_receive = Process(target=receiver.run)
    p_send = Process(target=sender.run)
    p_receive.start()
    p_send.start()
    print('Waiting...')
    p_send.join()
    print('Joined...')
    p_receive.join()
    print ('DONE')
if __name__ == '__main__':
    main()
