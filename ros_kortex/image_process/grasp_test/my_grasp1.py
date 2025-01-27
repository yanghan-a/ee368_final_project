#!/usr/bin/env python3
###
# KINOVA (R) KORTEX (TM)
#
# Copyright (c) 2019 Kinova inc. All rights reserved.
#
# This software may be modified and distributed
# under the terms of the BSD 3-Clause license.
#
# Refer to the LICENSE file for details.
#
###

import math
import sys

import numpy as np
import rospy
import time
from kortex_driver.srv import *
from kortex_driver.msg import *
from std_msgs.msg import Float32MultiArray

class ExampleCartesianActionsWithNotifications:
    def __init__(self):
        try:
            
            rospy.init_node('example_cartesian_poses_with_notifications_python')

            self.HOME_ACTION_IDENTIFIER = 2

            self.action_topic_sub = None
            self.all_notifs_succeeded = True

            self.all_notifs_succeeded = True

            self.start_grasp = False
            #订阅ggcnn中发来的点的位置
            print('类真的在声明')
            self.sub_ggcnn = rospy.Subscriber('ggcnn/out/command',Float32MultiArray,self.ggcnn_grasp_callback)
            
            # Get node params
            self.robot_name = rospy.get_param('~robot_name', "my_gen3_lite")
            self.is_gripper_present = rospy.get_param("/" + self.robot_name + "/is_gripper_present", True)
            rospy.loginfo("Using robot_name " + self.robot_name)

            # Init the action topic subscriber
            #用来记录机器人不同时刻的action状态
            self.action_topic_sub = rospy.Subscriber("/" + self.robot_name + "/action_topic", ActionNotification, self.cb_action_topic)
            self.last_action_notif_type = None

            # Init the services
            clear_faults_full_name = '/' + self.robot_name + '/base/clear_faults'
            rospy.wait_for_service(clear_faults_full_name)
            self.clear_faults = rospy.ServiceProxy(clear_faults_full_name, Base_ClearFaults)

            #读取关节将要运行的位置
            read_action_full_name = '/' + self.robot_name + '/base/read_action'
            rospy.wait_for_service(read_action_full_name)
            self.read_action = rospy.ServiceProxy(read_action_full_name, ReadAction)

            #执行关节运动
            execute_action_full_name = '/' + self.robot_name + '/base/execute_action'
            rospy.wait_for_service(execute_action_full_name)
            self.execute_action = rospy.ServiceProxy(execute_action_full_name, ExecuteAction)

            set_cartesian_reference_frame_full_name = '/' + self.robot_name + '/control_config/set_cartesian_reference_frame'
            rospy.wait_for_service(set_cartesian_reference_frame_full_name)
            self.set_cartesian_reference_frame = rospy.ServiceProxy(set_cartesian_reference_frame_full_name, SetCartesianReferenceFrame)

            #猜测是控制夹爪的服务
            send_gripper_command_full_name = '/' + self.robot_name + '/base/send_gripper_command'
            rospy.wait_for_service(send_gripper_command_full_name)
            self.send_gripper_command = rospy.ServiceProxy(send_gripper_command_full_name, SendGripperCommand)

            #激活发布机器人action状态的service
            activate_publishing_of_action_notification_full_name = '/' + self.robot_name + '/base/activate_publishing_of_action_topic'
            rospy.wait_for_service(activate_publishing_of_action_notification_full_name)
            self.activate_publishing_of_action_notification = rospy.ServiceProxy(activate_publishing_of_action_notification_full_name, OnNotificationActionTopic)

            get_product_configuration_full_name = '/' + self.robot_name + '/base/get_product_configuration'
            rospy.wait_for_service(get_product_configuration_full_name)
            self.get_product_configuration = rospy.ServiceProxy(get_product_configuration_full_name, GetProductConfiguration)

            validate_waypoint_list_full_name = '/' + self.robot_name + '/base/validate_waypoint_list'
            rospy.wait_for_service(validate_waypoint_list_full_name)
            self.validate_waypoint_list = rospy.ServiceProxy(validate_waypoint_list_full_name, ValidateWaypointList)
        except:
            self.is_init_success = False
        else:
            self.is_init_success = True
    def rotation_matrix_to_euler_angles(self,R):
        """
        Convert rotation matrix to Euler angles (yaw, pitch, roll).
        Assumes the rotation matrix represents rotations in ZYX order.
        """
        # Extract rotation angles
        theta_x = np.arctan2(R[2, 1], R[2, 2])
        theta_y = np.arctan2(-R[2, 0], math.sqrt(R[2,1]**2+R[2,2]**2))
        theta_z = np.arctan2(R[1, 0], R[0, 0])

        return np.array([theta_x, theta_y, theta_z])
    def ggcnn_grasp_callback(self,msg):
        if self.start_grasp == True:
            print('消息处理准备抓取')
            my_cartesian_speed = CartesianSpeed()
            my_cartesian_speed.translation = 0.1 # m/s
            my_cartesian_speed.orientation = 15  # deg/s
            x = msg.data[0]
            y = msg.data[1]
            z = msg.data[2]
            angle = msg.data[3]#-np.pi/2

            #物体相对于相机变换矩阵
            object2camera = [[np.cos(angle), -np.sin(angle),  0, x],
                             [np.sin(angle),  np.cos(angle),  0, y],
                             [ 0,            0,               1, z],
                             [ 0,            0,               0, 1]]

            
            #外参矩阵，相机相对于机械臂的base_linke
            '''
            [[ 0, -1,  0],
             [-1,  0,  0],
             [ 0,  0, -1]]

            [[ 0, -1,  0, 0.5+0.0106],
             [-1,  0,  0, 0.5+0.0175],
             [ 0,  0, -1, 1.1-0.0125],
             [ 0,  0,  0, 1         ]]
            '''
            camera2base_link = [[ 0, -1,  0, 0.5+0.0106],
                                [-1,  0,  0, 0.5+0.0175],
                                [ 0,  0, -1, 1.1-0.0125],
                                [ 0,  0,  0, 1         ]]
            object2base_link = np.dot(camera2base_link,object2camera)
            rotation = object2base_link[:3,:3]
            theta_x,theta_y,theta_z = self.rotation_matrix_to_euler_angles(rotation)
            print('theta_x:',theta_x)
            print('theta_y:',theta_y)
            print('theta_z:',theta_z)
            my_constrained_pose = ConstrainedPose()
            my_constrained_pose.constraint.oneof_type.speed.append(my_cartesian_speed)
            print(object2base_link)
            my_constrained_pose.target_pose.x = object2base_link[0][3]
            my_constrained_pose.target_pose.y = object2base_link[1][3]
            my_constrained_pose.target_pose.z = object2base_link[2][3]
            my_constrained_pose.target_pose.theta_x = np.degrees(theta_x)
            my_constrained_pose.target_pose.theta_y = np.degrees(theta_y)
            my_constrained_pose.target_pose.theta_z = np.degrees(theta_z)

            req = ExecuteActionRequest()
            req.input.oneof_action_parameters.reach_pose.append(my_constrained_pose)
            req.input.name = "pose1"
            req.input.handle.action_type = ActionType.REACH_POSE
            req.input.handle.identifier = 1001

            rospy.loginfo("Sending pose 1...")
            self.last_action_notif_type = None
            try:
                self.execute_action(req)
            except rospy.ServiceException:
                rospy.logerr("Failed to send pose 1")
                # success = False
            else:
                rospy.loginfo("Waiting for pose 1 to finish...")

            self.wait_for_action_end_or_abort()
            # Example of gripper command
            # Let's close the gripper at 50%
            if self.is_gripper_present:
                self.example_send_gripper_command(0.9)
            else:
                rospy.logwarn("No gripper is present on the arm.")
            self.start_grasp == False
            self.example_home_the_robot()

    def cb_action_topic(self, notif):
        self.last_action_notif_type = notif.action_event

    def wait_for_action_end_or_abort(self):
        while not rospy.is_shutdown():
            if (self.last_action_notif_type == ActionEvent.ACTION_END):
                rospy.loginfo("Received ACTION_END notification")
                return True
            elif (self.last_action_notif_type == ActionEvent.ACTION_ABORT):
                rospy.loginfo("Received ACTION_ABORT notification")
                self.all_notifs_succeeded = False
                return False
            else:
                time.sleep(0.01)

    def example_clear_faults(self):
        try:
            self.clear_faults()
        except rospy.ServiceException:
            rospy.logerr("Failed to call ClearFaults")
            return False
        else:
            rospy.loginfo("Cleared the faults successfully")
            rospy.sleep(2.5)
            return True

    def example_home_the_robot(self):
        # The Home Action is used to home the robot. It cannot be deleted and is always ID #2:

        #这里主要是定义ReadActionRequest()类型服务，再res = self.read_action(req)发送服务请求
        req = ReadActionRequest()
        req.input.identifier = self.HOME_ACTION_IDENTIFIER
        self.last_action_notif_type = None
        try:
            res = self.read_action(req)
        except rospy.ServiceException:
            rospy.logerr("Failed to call ReadAction")
            return False
        # Execute the HOME action if we could read it
        else:
            # What we just read is the input of the ExecuteAction service

            req = ExecuteActionRequest()
            req.input = res.output
            rospy.loginfo("Sending the robot home...")
            try:
                #调用执行服务self.execute_action(req)开始执行
                self.execute_action(req)
            except rospy.ServiceException:
                rospy.logerr("Failed to call ExecuteAction")
                return False
            else:
                return self.wait_for_action_end_or_abort()

    def example_set_cartesian_reference_frame(self):
        # Prepare the request with the frame we want to set
        req = SetCartesianReferenceFrameRequest()
        req.input.reference_frame = CartesianReferenceFrame.CARTESIAN_REFERENCE_FRAME_MIXED

        # Call the service
        try:
            self.set_cartesian_reference_frame()
        except rospy.ServiceException:
            rospy.logerr("Failed to call SetCartesianReferenceFrame")
            return False
        else:
            rospy.loginfo("Set the cartesian reference frame successfully")
            return True

        # Wait a bit
        rospy.sleep(0.25)

    #我的理解是调用self.activate_publishing_of_action_notification(req)服务，激活发布ActionNotification类型话题
    def example_subscribe_to_a_robot_notification(self):
        # Activate the publishing of the ActionNotification
        req = OnNotificationActionTopicRequest()
        rospy.loginfo("Activating the action notifications...")
        try:
            self.activate_publishing_of_action_notification(req)
        except rospy.ServiceException:
            rospy.logerr("Failed to call OnNotificationActionTopic")
            return False
        else:
            rospy.loginfo("Successfully activated the Action Notifications!")

        rospy.sleep(1.0)

        return True
    
    #调用self.send_gripper_command(req)来请求服务
    def example_send_gripper_command(self, value):
        # Initialize the request
        # Close the gripper
        req = SendGripperCommandRequest()
        finger = Finger()
        finger.finger_identifier = 0
        finger.value = value
        req.input.gripper.finger.append(finger)
        req.input.mode = GripperMode.GRIPPER_POSITION

        rospy.loginfo("Sending the gripper command...")

        # Call the service 
        try:
            self.send_gripper_command(req)
        except rospy.ServiceException:
            rospy.logerr("Failed to call SendGripperCommand")
            return False
        else:
            time.sleep(0.5)
            return True

    def main(self):
        # For testing purposes
        success = self.is_init_success
        try:
            rospy.delete_param("/kortex_examples_test_results/cartesian_poses_with_notifications_python")
        except:
            pass

        if success:

            #*******************************************************************************
            # Make sure to clear the robot's faults else it won't move if it's already in fault
            success &= self.example_clear_faults()
            #*******************************************************************************
            
            #*******************************************************************************
            # Start the example from the Home position
            success &= self.example_home_the_robot()
            #*******************************************************************************
            # Example of gripper command
            # Let's fully open the gripper
            if self.is_gripper_present:
                success &= self.example_send_gripper_command(0.4)
            else:
                rospy.logwarn("No gripper is present on the arm.")
            #*******************************************************************************
            # Set the reference frame to "Mixed"
            success &= self.example_set_cartesian_reference_frame()

            #*******************************************************************************
            # Subscribe to ActionNotification's from the robot to know when a cartesian pose is finished
            success &= self.example_subscribe_to_a_robot_notification()

            self.start_grasp = True

            #*******************************************************************************
            # Prepare and send pose 1
            # my_cartesian_speed = CartesianSpeed()
            # my_cartesian_speed.translation = 0.1 # m/s
            # my_cartesian_speed.orientation = 15  # deg/s

            # my_constrained_pose = ConstrainedPose()
            # my_constrained_pose.constraint.oneof_type.speed.append(my_cartesian_speed)

            # #最终矩阵
            # # T = np.array([[ 0.20277731, -0.88038933, -0.42871466,  0.34713418],
            # #                 [-0.94561191, -0.28977703,  0.14780907,  0.23260178],
            # #                 [-0.25436116, 0.37542538, -0.89126674,  0.14184948],
            # #                 [ 0.0,          0.0,        0.0  ,        1.0       ]])
            # my_constrained_pose.target_pose.x = 0.34713418
            # my_constrained_pose.target_pose.y = 0.23260178
            # my_constrained_pose.target_pose.z = 0.14184948
            # my_constrained_pose.target_pose.theta_x = 157.15787308
            # my_constrained_pose.target_pose.theta_y = 14.73573327
            # my_constrained_pose.target_pose.theta_z = -77.89677445

            # req = ExecuteActionRequest()
            # req.input.oneof_action_parameters.reach_pose.append(my_constrained_pose)
            # req.input.name = "pose1"
            # req.input.handle.action_type = ActionType.REACH_POSE
            # req.input.handle.identifier = 1001

            # rospy.loginfo("Sending pose 1...")
            # self.last_action_notif_type = None
            # try:
            #     self.execute_action(req)
            # except rospy.ServiceException:
            #     rospy.logerr("Failed to send pose 1")
            #     success = False
            # else:
            #     rospy.loginfo("Waiting for pose 1 to finish...")

            # self.wait_for_action_end_or_abort()
            # # Example of gripper command
            # # Let's close the gripper at 50%
            # if self.is_gripper_present:
            #     success &= self.example_send_gripper_command(0.5)
            # else:
            #     rospy.logwarn("No gripper is present on the arm.")   

            # # Prepare and send pose 2
            # req.input.handle.identifier = 1002
            # req.input.name = "pose2"

            # my_constrained_pose.target_pose.z = 0.3

            # req.input.oneof_action_parameters.reach_pose[0] = my_constrained_pose

            # rospy.loginfo("Sending pose 2...")
            # self.last_action_notif_type = None
            # try:
            #     self.execute_action(req)
            # except rospy.ServiceException:
            #     rospy.logerr("Failed to send pose 2")
            #     success = False
            # else:
            #     rospy.loginfo("Waiting for pose 2 to finish...")

            # self.wait_for_action_end_or_abort()

            # # Prepare and send pose 3
            # req.input.handle.identifier = 1003
            # req.input.name = "pose3"

            # my_constrained_pose.target_pose.x = 0.45

            # req.input.oneof_action_parameters.reach_pose[0] = my_constrained_pose

            # rospy.loginfo("Sending pose 3...")
            # self.last_action_notif_type = None
            # try:
            #     self.execute_action(req)
            # except rospy.ServiceException:
            #     rospy.logerr("Failed to send pose 3")
            #     success = False
            # else:
            #     rospy.loginfo("Waiting for pose 3 to finish...")

            # self.wait_for_action_end_or_abort()

            success &= self.all_notifs_succeeded
        
        # For testing purposes
        rospy.set_param("/kortex_examples_test_results/cartesian_poses_with_notifications_python", success)

        if not success:
            rospy.logerr("The example encountered an error.")
        rospy.spin()

if __name__ == "__main__":
    print('类的声明')
    ex = ExampleCartesianActionsWithNotifications()
    print('类已声明')
    ex.main()
