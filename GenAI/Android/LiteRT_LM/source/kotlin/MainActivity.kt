/*
 *===--MainActivity.kt--------------------------------------------------===//
 * Part of the Startup-Demos Project, under the MIT License
 * See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
 * for license information.
 * Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
 * SPDX-License-Identifier: MIT
 *===----------------------------------------------------------------------===//
 */

package com.example.litertlm

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.lifecycle.ViewModelProvider
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import kotlin.math.max

class MainActivity : AppCompatActivity() {
    
    private lateinit var viewModel: ChatViewModel
    private lateinit var chatRecyclerView: RecyclerView
    private lateinit var userInput: EditText
    private lateinit var loadingIndicator: ProgressBar
    private lateinit var errorMessage: TextView
    private lateinit var chatLayoutManager: LinearLayoutManager
    
    private var chatAdapter: ChatAdapter? = null
    private var isUserNearBottom = true
    private val bottomSnapThresholdPx by lazy {
        (48 * resources.displayMetrics.density).toInt()
    }
    
    // File picker result handler
    private val pickModelFileLauncher = registerForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri: Uri? ->
        uri?.let {
            val displayName = getDocumentName(it) ?: "model.litertlm"
            findViewById<EditText>(R.id.modelPathInput).setText(displayName)
            
            contentResolver.takePersistableUriPermission(it, Intent.FLAG_GRANT_READ_URI_PERMISSION)
            viewModel.setLoadingState(true)
            viewModel.initializeEngineWithUri(it, this)
        }
    }
    
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContentView(R.layout.activity_main)
        
        val rootView = findViewById<android.view.View>(R.id.main)
        val initialPaddingLeft = rootView.paddingLeft
        val initialPaddingTop = rootView.paddingTop
        val initialPaddingRight = rootView.paddingRight
        val initialPaddingBottom = rootView.paddingBottom

        ViewCompat.setOnApplyWindowInsetsListener(rootView) { v, insets ->
            val systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            val ime = insets.getInsets(WindowInsetsCompat.Type.ime())
            val bottomInset = max(systemBars.bottom, ime.bottom)

            v.setPadding(
                initialPaddingLeft + systemBars.left,
                initialPaddingTop + systemBars.top,
                initialPaddingRight + systemBars.right,
                initialPaddingBottom + bottomInset
            )
            insets
        }
        
        viewModel = ViewModelProvider(this).get(ChatViewModel::class.java)
        
        setupUI()
        observeViewModel()
        setupListeners()
    }
    
    private fun setupUI() {
        chatRecyclerView = findViewById(R.id.chatRecyclerView)
        userInput = findViewById(R.id.userInput)
        loadingIndicator = findViewById(R.id.loadingIndicator)
        errorMessage = findViewById(R.id.errorMessage)
        
        chatLayoutManager = LinearLayoutManager(this)
        chatRecyclerView.layoutManager = chatLayoutManager
        chatRecyclerView.itemAnimator = null
        chatAdapter = ChatAdapter(emptyList())
        chatRecyclerView.adapter = chatAdapter
        chatRecyclerView.addOnScrollListener(object : RecyclerView.OnScrollListener() {
            override fun onScrolled(recyclerView: RecyclerView, dx: Int, dy: Int) {
                updatePinnedToBottomState()
            }
        })
    }
    
    private fun observeViewModel() {
        viewModel.messages.observe(this) { messages ->
            val shouldAutoScroll = isUserNearBottom || chatAdapter?.itemCount == 0
            chatAdapter?.updateMessages(messages)
            if (shouldAutoScroll && messages.isNotEmpty()) {
                scrollToBottom()
            }
        }
        
        viewModel.isLoading.observe(this) { isLoading ->
            loadingIndicator.visibility = if (isLoading) android.view.View.VISIBLE else android.view.View.GONE
            findViewById<Button>(R.id.sendButton).isEnabled = !isLoading
        }
        
        viewModel.error.observe(this) { error ->
            error?.let {
                errorMessage.text = it
                errorMessage.visibility = android.view.View.VISIBLE
                Toast.makeText(this, it, Toast.LENGTH_SHORT).show()
            } ?: run {
                errorMessage.visibility = android.view.View.GONE
            }
        }
    }
    
    private fun setupListeners() {
        findViewById<Button>(R.id.browseButton).setOnClickListener {
            pickModelFileLauncher.launch(arrayOf("*/*"))
        }
        
        findViewById<Button>(R.id.sendButton).setOnClickListener {
            val message = userInput.text.toString().trim()
            if (message.isEmpty()) {
                Toast.makeText(this, R.string.litertlm_error_message_empty, Toast.LENGTH_SHORT).show()
            } else {
                viewModel.sendMessage(message)
                userInput.text.clear()
            }
        }
    }

    private fun updatePinnedToBottomState() {
        val itemCount = chatAdapter?.itemCount ?: 0
        if (itemCount == 0) {
            isUserNearBottom = true
            return
        }

        val distanceToBottom = chatRecyclerView.computeVerticalScrollRange() -
            chatRecyclerView.computeVerticalScrollOffset() -
            chatRecyclerView.computeVerticalScrollExtent()

        isUserNearBottom = distanceToBottom <= bottomSnapThresholdPx
    }

    private fun scrollToBottom() {
        val lastIndex = (chatAdapter?.itemCount ?: 0) - 1
        if (lastIndex < 0) {
            return
        }

        chatRecyclerView.post {
            val remainingScroll = chatRecyclerView.computeVerticalScrollRange() -
                chatRecyclerView.computeVerticalScrollOffset() -
                chatRecyclerView.computeVerticalScrollExtent()

            if (remainingScroll > 0) {
                chatRecyclerView.scrollBy(0, remainingScroll)
            }

            updatePinnedToBottomState()
        }
    }
    
    private fun getDocumentName(uri: Uri): String? {
        return contentResolver.query(uri, null, null, null, null)?.use { cursor ->
            if (cursor.moveToFirst()) {
                val index = cursor.getColumnIndex(android.provider.OpenableColumns.DISPLAY_NAME)
                if (index >= 0) cursor.getString(index) else null
            } else null
        }
    }
}
