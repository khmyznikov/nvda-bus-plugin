# -*- coding: utf-8 -*-
# NVDA Text Bridge Plugin
# A global plugin that captures NVDA speech output and logs it to the View Log

import sys
import time
import globalPluginHandler
import speech
from logHandler import log

# Python 2/3 compatibility
if sys.version_info[0] >= 3:
	unicode = str

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	"""
	NVDA Text Bridge Global Plugin
	Captures all text spoken by NVDA and outputs it to the View Log
	"""
	
	def __init__(self):
		"""Initialize the plugin and set up speech interception"""
		super().__init__()
		
		# Initialize capture state
		self._captureEnabled = True
		
		# Store original speech function
		self._originalSpeak = speech.speech.speak
		
		# Replace speech.speak with our custom function
		speech.speech.speak = self._interceptSpeak
		
		log.info("NVDA Text Bridge: Plugin initialized - speech capture enabled")
	
	def terminate(self):
		"""Clean up when plugin is terminated"""
		try:
			# Restore original speech function
			speech.speech.speak = self._originalSpeak			
			log.info("NVDA Text Bridge: Plugin terminated - speech capture disabled")
		except Exception as e:
			log.error(f"NVDA Text Bridge: Error during termination: {e}")
		
		super(GlobalPlugin, self).terminate()
	
	def _interceptSpeak(self, speechSequence, *args, **kwargs):
		"""
		Intercept speech calls and log the text content
		
		Args:
			speechSequence: The speech sequence to be spoken
			*args, **kwargs: Additional arguments passed to speech.speak
		"""
		try:
			# Only process if capture is enabled
			if self._captureEnabled:
				# Log the raw speech sequence for debugging
				log.debug(f"NVDA Text Bridge: Raw speech sequence: {speechSequence}")
				
				# Extract text content from speech sequence
				text_content = self._extractTextFromSequence(speechSequence)
				
				if text_content.strip():
					# Log the captured text with timestamp
					timestamp = time.strftime("%H:%M:%S", time.localtime())
					log.info(f"NVDA Text Bridge [{timestamp}]: {text_content}")
				
		except Exception as e:
			# Log errors but don't interrupt speech
			log.error(f"NVDA Text Bridge: Error capturing speech: {e}")
			log.debug(f"Error details: {str(e)}", exc_info=True)
		
		# Call the original speak function to maintain normal NVDA operation
		return self._originalSpeak(speechSequence, *args, **kwargs)
	
	def _extractTextFromSequence(self, speechSequence):
		"""
		Extract readable text from a speech sequence
		
		Args:
			speechSequence: NVDA speech sequence (list or single item)
			
		Returns:
			str: Extracted text content
		"""
		text_parts = []
		
		# Handle different types of speech sequences
		if isinstance(speechSequence, list):
			for item in speechSequence:
				text_parts.append(self._processSequenceItem(item))
		else:
			text_parts.append(self._processSequenceItem(speechSequence))
		
		# Join all text parts and clean up
		full_text = " ".join(text_parts)
		return full_text.strip()
	
	def _processSequenceItem(self, item):
		"""
		Process individual items in a speech sequence
		
		Args:
			item: Individual speech sequence item
			
		Returns:
			str: Text representation of the item
		"""
		try:
			# Handle string items (most common)
			if isinstance(item, str):
				return item
			
			# Handle unicode strings
			elif isinstance(item, unicode):
				return item
			
			# Handle speech commands and other objects
			elif hasattr(item, '__str__'):
				str_repr = str(item)
				# Filter out speech commands that start with special characters
				if not str_repr.startswith('<') and not str_repr.startswith('_'):
					return str_repr
			
			return ""
			
		except Exception as e:
			log.debug(f"NVDA Text Bridge: Error processing sequence item: {e}")
			return ""
	
	def script_toggleTextCapture(self, gesture):
		"""
		Script to toggle text capture on/off
		Can be bound to a gesture if needed
		"""
		if hasattr(self, '_captureEnabled'):
			self._captureEnabled = not self._captureEnabled
		else:
			self._captureEnabled = False
		
		status = "enabled" if self._captureEnabled else "disabled"
		log.info(f"NVDA Text Bridge: Text capture {status}")
	
	# Gesture binding (optional)
	__gestures = {
		# Uncomment and modify if you want to bind a key combination
		# "kb:NVDA+shift+t": "toggleTextCapture",
	}
