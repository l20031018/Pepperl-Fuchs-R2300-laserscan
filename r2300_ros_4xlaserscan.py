#!/usr/bin/env python

import rospy
from sensor_msgs.msg import LaserScan
import struct as st
import urllib2
import ConfigParser
import json
import socket
from threading import Thread, Lock
import Queue
import random
import bisect

mute = Lock()
port=random.randint(16000,19000)
q = Queue.Queue(200)
q1 = Queue.Queue(200)
pc=LaserScan()
print pc.header
conf = ConfigParser.ConfigParser()
conf.read('conf.ini')
ip = conf.get('ip_address', 'ip')
local_ip = conf.get('ip_address', 'local_ip')
request_handle = 'http://' + ip+ '/cmd/request_handle_udp?address=' + local_ip + '&port=' + str(port)+' HTTP/1.0'
request_scanoutput = 'http://' + ip + '/cmd/start_scanoutput?handle=default HTTP/1.0'
set_f_l = 'http://' + ip + '/cmd/set_parameter?scan_frequency=50&pilot_enable=off'



def getvalue(points):
    distance = []
    intensities = []
    i = 0
    #print len(points[0:4])
    while i<len(points):

        s=st.unpack('<I',points[i:i+4])
        intensities.append((s[0]>>20)&0xfff)
        distance.append(float(s[0]&0xfffff)/1000)
        i+=4
    return distance,intensities

def pailie():
    global mute,q
    layer0=[]
    layer1=[]
    layer2=[]
    layer3=[]
    iS_layer_full=0
    point=b''
    while iS_layer_full!=1:
        #mute.acquire()
        if q.qsize!=0:
            try:
                e=q.get(timeout=1)
            except:
                print 'q get error'
            #mute.release()

        else:
            mute.release()
            pass
        #print 'points in this pack is %d' %len(e[-1])
        if e[2]==0:
            bisect.insort_right(layer0,e)
        if e[2]==1:
            bisect.insort_right(layer1,e)
        if e[2]==2:
            bisect.insort_right(layer2,e)
        if e[2]==3:
            bisect.insort_right(layer3,e)
        if len(layer0)==4 and len(layer1)==4 and len(layer2)==4 and len(layer3)==4:
            iS_layer_full=1


    return layer0[0][-1]+layer0[1][-1]+layer0[2][-1]+layer0[3][-1],layer1[0][-1]+layer1[1][-1]+layer1[2][-1]+layer1[3][-1],layer2[0][-1]+layer2[1][-1]+layer2[2][-1]+layer2[3][-1],layer3[0][-1]+layer3[1][-1]+layer3[2][-1]+layer3[3][-1]

def from_bytes(data):
    package_header=st.unpack('<HHIHHHHQIIHHHii',data[0:46])
    num_points_packet=package_header[11]
    layer_index=package_header[6]
    header_size=package_header[3]    #not sure
    angular_increment=package_header[-1]
    packet_number=package_header[5]
    scan_number=package_header[4]
    point=data[header_size:]
    first_index=package_header[12]
    first_angle=package_header[13]
    return [packet_number,scan_number,layer_index,num_points_packet,first_index,first_angle,angular_increment,point]

def request_datas():
    response = urllib2.urlopen(set_f_l)
    response = urllib2.urlopen(request_handle)
    j = response.read()
    result=json.loads(j)
    if result["error_code"]==0 and result["error_text"]=='success':
        response = urllib2.urlopen(request_scanoutput)
        j = response.read()
        result=json.loads(j)
        if result["error_code"]==0 and result["error_text"]=='success':
            print 'start scanoutput done'
        else:
            print 'fail'
    else:
        print 'fail'


class ProducerThread(Thread):

    #def __init__(self):
    #    super(ProducerThread, self).__init__()

    def run(self):
        global local_ip, port, q
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(("10.0.10.6", port))
        print 'Bind UDP On Port 16435..'
        while True:
            data, addr = s.recvfrom(2000)
            #print 'lenth of data is %d' %len(data)
            #if data[0:2] == b'\x5c\x2a':
                #data += s.recvfrom()(st.unpack('<I', data[4:]))
            a = from_bytes(data)
            #print a
            #print len(a[-1])
            q.put(a)


class ConsumerThread(Thread):

    #def __init__(self):
    #    super(ConsumerThread, self).__init__()


    def run(self):
        global q,q1
        while True:
            #mute.acquire()
            if q.qsize!=0:
                s=pailie()[2]
                print '3'
                s1=getvalue(s)
                print '4'
                q1.put(s1,timeout=3)
                print 'put into Q done'
                print 'Q zise is %d' %q1.qsize()
                print '5'
                #mute.release()
            else:
                print 'waiting for q'
                #mute.release()
                pass


if __name__ == '__main__':
    rospy.init_node("R2300_4")
    pub_data = rospy.Publisher('R2300/data', LaserScan, queue_size=1)
    frame_id = rospy.get_param('~frame_id', 'R2300_datas')
    frequency = rospy.get_param('frequency', 100)
    rate = rospy.Rate(frequency)
    seq = 0
    pc.header.frame_id = frame_id
    pc.angle_min = -0.872665
    pc.angle_max = 0.872665
    pc.angle_increment = 0.001745
    pc.scan_time = 0.08
    pc.range_min = 0.2
    pc.range_max = 10
    request_datas()
    producer=ProducerThread()
    consumer=ConsumerThread()
    producer.start()
    #ProducerThread().join()
    consumer.start()
    #ConsumerThread().join()

    print rospy.is_shutdown()
    while 1:
        print 'q size is %d' %q.qsize()
        print 'Q size is %d' %q1.qsize()
        print 'ConsumerThread is ', consumer.is_alive()
        print 'ProducerThread is ', producer.is_alive()
        print q1.qsize()!=0
        try:
            scans=q1.get(timeout=0.01)
            print 'get from Q done'
            print '1'
            pc.header.stamp = rospy.Time.now()
            pc.header.seq = seq
            pc.ranges=scans[0]
            pc.intensities=scans[1]
            pub_data.publish(pc)
            print '2'
            seq+=1
            rate.sleep()
        except:
            print 'get from Q error'

