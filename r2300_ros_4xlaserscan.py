#!/usr/bin/env python

'''
Pepperl-Fuchs  R2300  ROS driver
Frame id:R2300_datas
Topic:R2300/data(msg type:LaserScan, output:layer2)
test on ros_indigo python 2.7

author: Ding Yi
email:l20031018@126.com

'''

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
port = random.randint(16000, 19000)
q = Queue.Queue(200)
q1 = Queue.Queue(200)
pc = LaserScan()
print pc.header
conf = ConfigParser.ConfigParser()
conf.read('conf.ini')
ip = conf.get('ip_address', 'ip')
local_ip = conf.get('ip_address', 'local_ip')
selected_layer = int(conf.get('option', 'layer'))
request_handle = 'http://' + ip + '/cmd/request_handle_udp?address=' + local_ip + '&port=' + str(port) + ' HTTP/1.0'
request_scanoutput = 'http://' + ip + '/cmd/start_scanoutput?handle=default HTTP/1.0'
set_f_l = 'http://' + ip + '/cmd/set_parameter?scan_frequency=50&pilot_enable=off'



def getvalue(points):
    distance = []
    intensities = []
    i = 0
    #print len(points[0:4])
    while i < len(points):

        s = st.unpack('<I',points[i:i+4])
        intensities.append((s[0]>>20)&0xfff)
        distance.append(float(s[0]&0xfffff)/1000)
        i += 4
    return distance, intensities

def pailie():
    global mute, q, selected_layer
    layer0 = []
    layer1 = []
    layer2 = []
    layer3 = []
    iS_layer_full = 0
    while iS_layer_full != 1:

        try:
            e = q.get()
        except:
            print 'q get error'
        if e[2] == selected_layer and len(layer2) < 4:
            bisect.insort_right(layer2, e)
        if len(layer2) == 4:
            iS_layer_full = 1

    return layer2[0][-1] + layer2[1][-1] + layer2[2][-1] + layer2[3][-1]


def from_bytes(data):
    package_header = st.unpack('<HHIHHHHQIIHHHii',data[0:46])
    num_points_packet = package_header[11]
    layer_index = package_header[6]
    header_size = package_header[3]    #not sure
    angular_increment = package_header[-1]
    packet_number = package_header[5]
    scan_number = package_header[4]
    point = data[header_size:]
    first_index = package_header[12]
    first_angle = package_header[13]
    return [packet_number, scan_number, layer_index, num_points_packet, first_index, first_angle, angular_increment, point]


def request_datas():
    response = urllib2.urlopen(set_f_l)
    response = urllib2.urlopen(request_handle)
    j = response.read()
    result = json.loads(j)
    if result["error_code"] == 0 and result["error_text"] == 'success':
        response = urllib2.urlopen(request_scanoutput)
        j = response.read()
        result = json.loads(j)
        if result["error_code"] == 0 and result["error_text"] == 'success':
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
        print 'Bind UDP On Port %d..' %port
        while True:
            data, addr = s.recvfrom(2000)
            a = from_bytes(data)
            q.put(a)


class ConsumerThread(Thread):

    def run(self):
        global q, q1
        while True:
            s = pailie()
            s1 = getvalue(s)
            try:
                q1.put(s1, False)
            except:
                pass

if __name__ == '__main__':
    rospy.init_node("R2300_4")
    pub_data = rospy.Publisher('R2300/data', LaserScan, queue_size=1)
    frame_id = rospy.get_param('~frame_id', 'R2300_datas')
    frequency = rospy.get_param('frequency', 20)
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
    producer = ProducerThread()
    consumer = ConsumerThread()
    producer.start()
    #ProducerThread().join()
    consumer.start()
    #ConsumerThread().join()

    print rospy.is_shutdown()
    while 1:
        try:
            scans = q1.get(False)
            pc.header.stamp = rospy.Time.now()
            pc.header.seq = seq
            pc.ranges = scans[0]
            pc.intensities = scans[1]
            pub_data.publish(pc)
            seq += 1
            rate.sleep()
        except:
            #print 'get from Q error'
            pass

