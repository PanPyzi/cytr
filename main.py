import socketcan
import json
import os
#Init important vars

interface = "can1"
socket = socketcan.CanRawSocket(interface=interface)





def read():
    print("start read and save")
    while True:
        frame = socket.recv()
        can_data_B = frame.data
        can_data = []
        can_id = str(hex(frame.can_id))
        if(can_id =='0x161'):   
            for i in range(0, len(frame.data.hex()))[::2]:
                can_data.append(frame.data.hex()[i] + frame.data.hex()[i + 1])
            FUEL_D = (int(str(can_data[0]), 16))*32.45
            #print((int(str(can_data[3]), 16)))#0-64 paliwko

        elif (can_id == '0x0f6'):
            for i in range(0, len(frame.data.hex()))[::2]:
                can_data.append(frame.data.hex()[i] + frame.data.hex()[i + 1])
            DISTANCE_TOT_D = int(str(can_data[4]) + str(can_data[5] + str(can_data[6]) + str(can_data[7]) + str(can_data[8])+ str(can_data[9])), 16)
            OUTSIDE_TEMP_D = round(((int(str(can_data[12]) + str(can_data[13])))/2.0)-39.5,1)
            # print((int(str(can_data[1])+str(can_data[2]), 16))/100)

        elif (can_id == '0x036'):
            for i in range(0, len(frame.data.hex()))[::2]:
                can_data.append(frame.data.hex()[i] + frame.data.hex()[i + 1])
            BATTERY_ECO_D = str(bin(int(can_data[5], 16)))[0:1] #batterylight economic
            BRIGHTNESS_D = (int(str(can_data[8]), 16))
            IGNITION_E = str(bin(int(can_data[10], 16)))[2:4] #01-on 10-off

        elif (can_id == '0x0e6'):
            for i in range(0, len(frame.data.hex()))[::2]:
                can_data.append(frame.data.hex()[i] + frame.data.hex()[i + 1])
            VOLTS_C = (int(str(can_data[14]) + str(can_data[15]), 16)+144)/20 # mabey

        elif (can_id == '0x128'):
            for i in range(0, len(frame.data.hex()))[::2]:
                can_data.append(frame.data.hex()[i] + frame.data.hex()[i + 1])
            FUEL_L_D = str(bin(int(can_data[0], 16)))[2:4] #fuel light
            DOOR_D = str(bin(int(can_data[3], 16)))[2:4]  # Door open
            LIGHTS_D = str(bin(int(can_data[9], 16))) # przeciwmgielne dlugie krotkie postojowe
            LIGHTS2_D = str(bin(int(can_data[10], 16))) #signals and przeiwmbielne tyl

        elif (can_id == '0x168'):
            for i in range(0, len(frame.data.hex()))[::2]:
                can_data.append(frame.data.hex()[i] + frame.data.hex()[i + 1])
            HEAT_OILF_D = str(bin(int(can_data[0], 16)))  # 2 overheat(flashing), 4 oil light (flashing), 8 overheat (on), f oil and overheat flashing
            BREAK_OIL_D = str(bin(int(can_data[1], 16))) # 4= brake (on), 8 oil light(on)
            CHK_F_D = str(bin(int(can_data[7], 16)))  # 1 = fuel bar (flashing), 2 check engine (on)
            CHK_L_D = str(bin(int(can_data[8], 16)))  # 1 check engine (flashing), 2 airbag,
            BATTERY_L_D = str(bin(int(can_data[9], 16))) # 2,4 = battery light (on)
            BATTERY_LF_D = str(bin(int(can_data[14], 16)))  # 8= battery light(flashing)

        elif(can_id =='0x1a8'):
            for i in range(0, len(frame.data.hex()))[::2]:
                can_data.append(frame.data.hex()[i] + frame.data.hex()[i + 1])
            SPEED_D = (int(str(can_data[1])+str(can_data[2]), 16))/100
            #print((int(str(can_data[1])+str(can_data[2]), 16))/100)
            
        elif(can_id =='0xb6'):
            for i in range(0, len(frame.data.hex()))[::2]:
                can_data.append(frame.data.hex()[i] + frame.data.hex()[i + 1])
            RPM_D = (int(str(can_data[0]), 16))*32.45
            #print((int(str(can_data[2]), 16))*2.66)
        os.system("clear")
        print(FUEL_D)
        print(DISTANCE_TOT_D)
        print(OUTSIDE_TEMP_D)
        print(BATTERY_ECO_D)
        print(BRIGHTNESS_D)
        print(IGNITION_E)
        print(VOLTS_C)
        print(FUEL_L_D)
        print(HEAT_OILF_D)
        print(BREAK_OIL_D)
        print(CHK_F_D)
        print(CHK_L_D)
        print(BATTERY_L_D)
        print(BATTERY_LF_D)
        print(SPEED_D)
        print(RPM_D)



read()



