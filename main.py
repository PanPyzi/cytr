import socketcan
import json
#Init important vars

interface = "can0"
socket = socketcan.CanRawSocket(interface=interface)





def read_and_save():
    can_data_s = {}
    can_data = [[],[]]
    a=0
    while True:
        frame = socket.recv()
        can_data_B = frame.data


        can_id = str(hex(frame.can_id))
        for i in range(0, len(frame.data.hex()))[::2]:
            can_data_s[can_id].append(frame.data.hex()[i] + frame.data.hex()[i + 1])
            can_data[a].append(frame.data.hex()[i] + frame.data.hex()[i + 1])
        a=a+1

def read_and_mark():
    can_data_s = {}
    while True:
        mark=input("Marking: ")
        if mark!="stop":


            for v in range(0,20):
                can_data_tmp=[]
                frame = socket.recv()
                for i in range(0, len(frame.data.hex()))[::2]:
                    can_data_tmp.append(frame.data.hex()[i] + frame.data.hex()[i + 1])
                can_data_s[mark].append(can_data_tmp)

        else:
            f = open("can_data_marked.txt", "w")
            f.write(json.dumps(can_data_s))
            return


def keep_alive():
    can_id = 0x123
    data = bytes(range(0, 0x88, 0x11))
    frame1 = socketcan.CanFrame(can_id=can_id, data=data)

    socketcan.send(frame1)

read_and_mark()