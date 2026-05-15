/*
 *===--ChatViewModel.kt-------------------------------------------------===//
 * Part of the Startup-Demos Project, under the MIT License
 * See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
 * for license information.
 * Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
 * SPDX-License-Identifier: MIT
 *===----------------------------------------------------------------------===//
 */

package com.example.litertlm

import android.content.Context
import android.net.Uri
import android.util.Log
import androidx.lifecycle.LiveData
import androidx.lifecycle.MutableLiveData
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.google.ai.edge.litertlm.Engine
import com.google.ai.edge.litertlm.EngineConfig
import com.google.ai.edge.litertlm.Message
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.launch
import java.io.File

class ChatViewModel : ViewModel() {
    
    private val _messages = MutableLiveData<List<ChatMessage>>(emptyList())
    val messages: LiveData<List<ChatMessage>> = _messages
    
    private val _isLoading = MutableLiveData<Boolean>(false)
    val isLoading: LiveData<Boolean> = _isLoading
    
    private val _error = MutableLiveData<String?>()
    val error: LiveData<String?> = _error
    
    private var engine: Engine? = null
    private var conversation: com.google.ai.edge.litertlm.Conversation? = null
    
    /**
     * Initialize engine with a URI (e.g., from file picker)
     */
    fun initializeEngineWithUri(uri: Uri, context: Context) {
        viewModelScope.launch(Dispatchers.IO) {
            try {
                val inputStream = context.contentResolver.openInputStream(uri)
                    ?: throw Exception("Cannot open model file")
                
                val cacheFile = File(context.cacheDir, "model.litertlm")
                inputStream.use { input -> 
                    cacheFile.outputStream().use { output -> input.copyTo(output) } 
                }
                
                initializeEngine(cacheFile.absolutePath)
            } catch (e: Exception) {
                handleError("Failed to load model file: ${e.message}")
            }
        }
    }
    
    /**
     * Initialize engine with local file path
     */
    private fun initializeEngine(modelPath: String) {
        setLoading(true)
        try {
            val engineConfig = EngineConfig(
                modelPath = modelPath,
                backend = com.google.ai.edge.litertlm.Backend.CPU()
            )
            
            engine = Engine(engineConfig).apply { initialize() }
            conversation = engine!!.createConversation()
            
            setLoading(false)
            Log.d("ChatViewModel", "Engine initialized: $modelPath")
        } catch (e: Exception) {
            handleError("Failed to initialize engine: ${e.message}")
        }
    }
    
    /**
     * Send message and stream response
     */
    fun sendMessage(userText: String) {
        if (conversation == null) {
            handleError("Engine not initialized")
            return
        }
        
        if (userText.isBlank()) return
        
        val userMessage = ChatMessage("user", userText)
        _messages.postValue(_messages.value.orEmpty() + userMessage)
        
        viewModelScope.launch(Dispatchers.IO) {
            try {
                val responseBuilder = StringBuilder()
                conversation!!
                    .sendMessageAsync(userText)
                    .catch { e -> handleError("Error: ${e.message}") }
                    .collect { message: Message ->
                        responseBuilder.append(message.toString())
                        updateModelMessage(responseBuilder.toString())
                    }
            } catch (e: Exception) {
                handleError("Error: ${e.message}")
            }
        }
    }
    
    private fun updateModelMessage(text: String) {
        val modelMessage = ChatMessage("model", text)
        val messages = _messages.value.orEmpty().toMutableList()
        
        if (messages.lastOrNull()?.role == "model") {
            messages[messages.lastIndex] = modelMessage
        } else {
            messages.add(modelMessage)
        }
        
        _messages.postValue(messages)
    }
    
    private fun setLoading(loading: Boolean) {
        _isLoading.postValue(loading)
    }
    
    fun setLoadingState(loading: Boolean) {
        setLoading(loading)
    }
    
    private fun handleError(message: String) {
        _error.postValue(message)
        setLoading(false)
        Log.e("ChatViewModel", message)
    }
    
    override fun onCleared() {
        super.onCleared()
        try {
            conversation?.close()
            engine?.close()
        } catch (e: Exception) {
            Log.e("ChatViewModel", "Error closing resources", e)
        }
    }
}
