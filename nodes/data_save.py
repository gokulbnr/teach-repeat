#!/usr/bin/env python

import rospy
import cv2
import numpy as np
import os
import tf2_ros
import datetime
import json
from std_srvs.srv import Trigger, TriggerResponse
from rospy_message_converter import message_converter

import teach_repeat.image_processing as image_processing
from teach_repeat.srv import SaveImageAndPose, SaveImageAndPoseResponse

class data_save:

	def __init__(self):
		self.setup_parameters()
		self.setup_publishers()
		self.setup_subscribers()

	def setup_parameters(self):
		self.ready = not rospy.get_param('/wait_for_ready', False)
		self.save_id = 0
		self.save_dir = os.path.expanduser(rospy.get_param('~save_dir', '~/miro/data'))
		self.save_full_res_images = rospy.get_param('/save_full_res_images', True)
		self.save_gt_data = rospy.get_param('/save_gt_data', False)
		self.timestamp_dir = rospy.get_param('~timestamp_folder', False)
		if self.save_dir[-1] != '/':
			self.save_dir += '/'
		if self.timestamp_dir:
			self.save_dir += datetime.datetime.now().strftime('%Y-%m-%d_%H:%M:%S/')
		if not os.path.isdir(self.save_dir):
			os.makedirs(self.save_dir)
		if self.save_full_res_images:
			if not os.path.isdir(self.save_dir+'full/'):
				os.makedirs(self.save_dir+'full/')
		if not os.path.isdir(self.save_dir+'norm/'):
			os.makedirs(self.save_dir+'norm/')
		self.resize = image_processing.make_size(height=rospy.get_param('/image_resize_height', None), width=rospy.get_param('/image_resize_width', None))
		if self.resize[0] is None and self.resize[1] is None:
			self.resize = None

		self.patch_size = image_processing.parse_patch_size_parameter(rospy.get_param('/patch_size', (9,9)))

		self.save_params()

	def setup_publishers(self):
		pass

	def setup_subscribers(self):
		if not self.ready:
			self.srv_ready = rospy.Service('ready_data_save', Trigger, self.on_ready)
		self.tfBuffer = tf2_ros.Buffer()
		self.tfListener = tf2_ros.TransformListener(self.tfBuffer)
		rospy.sleep(0.2)
		self.service = rospy.Service('save_image_pose', SaveImageAndPose, self.process_image_and_pose)

	def save_params(self):
		params = {
			'resize': self.resize,
			'patch_size': self.patch_size
		}
		with open(self.save_dir + 'params.txt', 'w') as params_file:
			params_file.write(json.dumps(params))

	def on_ready(self, srv):
		if not self.ready:
			self.ready = True
			return TriggerResponse(success=True)
		else:
			return TriggerResponse(success=False, message="Data save already started.")

	def process_image_and_pose(self, request):
		if self.ready:
			image = image_processing.msg_to_image(request.image)
			pose = request.pose
			id = "%06d" % (self.save_id)
			normalised_image = image_processing.patch_normalise_image(image, self.patch_size, resize=self.resize)
			message_as_text = json.dumps(message_converter.convert_ros_message_to_dictionary(pose))

			if self.save_gt_data:
				try:
					trans = self.tfBuffer.lookup_transform('map', 'base_link', rospy.Time())
					trans_as_text = json.dumps(message_converter.convert_ros_message_to_dictionary(trans))
					with open(self.save_dir + id + '_map_to_base_link.txt', 'w') as pose_file:
						pose_file.write(trans_as_text)
				except (tf2_ros.LookupException, tf2_ros.ConnectivityException, tf2_ros.ExtrapolationException):
					print('Could not lookup transform from /map to /base_link')
					pass
			
			if self.save_full_res_images:
				cv2.imwrite(self.save_dir+'full/'+id+'.png', image)
			cv2.imwrite(self.save_dir+'norm/'+id+'.png', np.uint8(255.0 * (1 + normalised_image) / 2.0))
			with open(self.save_dir+id+'_pose.txt', 'w') as pose_file:
				pose_file.write(message_as_text)
			self.save_id += 1
			print('saved frame %d' % self.save_id)
			return SaveImageAndPoseResponse(success=True)


if __name__ == "__main__":
	rospy.init_node("data_save")
	saver = data_save()
	rospy.spin()
