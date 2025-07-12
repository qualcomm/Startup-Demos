package com.example.inferencecloudchat

import android.view.View
import android.view.MotionEvent
import android.view.inputmethod.EditorInfo
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.RecyclerView
import androidx.recyclerview.widget.LinearLayoutManager

import java.io.IOException

import okhttp3.Call
import okhttp3.Callback
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response

import org.json.JSONException
import org.json.JSONObject
import org.json.JSONArray

import androidx.core.widget.doAfterTextChanged


class MainActivity : AppCompatActivity() {
    lateinit var recyclerView: RecyclerView
    lateinit var welcomeTextView: TextView
    lateinit var messageEditText: EditText
    lateinit var apiKeyEditText: EditText
    lateinit var sendButton: ImageButton
    lateinit var messageList: MutableList<Message>
    lateinit var messageAdapter: MessageAdapter
    lateinit var endPointSpinner: Spinner
    lateinit var llmModelSpinner: Spinner
    lateinit var selectedApiEndpoint: String
    lateinit var selectedApiKey: String
    lateinit var selectedModel: String
    var llmModels: MutableList<String> = mutableListOf("Llama-3.1-8B")

    override fun onCreate(savedInstanceState: android.os.Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        messageList = mutableListOf<Message>()

        recyclerView = findViewById<RecyclerView>(R.id.recycler_view)
        welcomeTextView = findViewById<android.widget.TextView>(R.id.welcome_text)
        messageEditText = findViewById<EditText>(R.id.message_edit_text)
        apiKeyEditText = findViewById<EditText>(R.id.editTextTextPassword)
        endPointSpinner = findViewById(R.id.spinnerEndPoint)
        llmModelSpinner = findViewById(R.id.spinnerModel)


        sendButton = findViewById<ImageButton>(R.id.send_btn)
        // Load the array from resources
        val apiEndpoints = resources.getStringArray(R.array.api_endpoints)
        selectedApiEndpoint = apiEndpoints[0] // Default to first item
        val adapter = ArrayAdapter(this, android.R.layout.simple_spinner_item, apiEndpoints)
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item)
        endPointSpinner.adapter = adapter
        selectedApiKey = getString(R.string.api_key)

        endPointSpinner.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>, view: View, position: Int, id: Long) {
                selectedApiEndpoint = parent.getItemAtPosition(position).toString()
                Toast.makeText(this@MainActivity, "Selected: $selectedApiEndpoint", Toast.LENGTH_SHORT).show()
            }

            override fun onNothingSelected(parent: AdapterView<*>) {}
        }

        selectedModel = llmModels[0] // Default to first item
        val adapter_llm = ArrayAdapter(this, android.R.layout.simple_spinner_item, llmModels)
        adapter_llm.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item)
        llmModelSpinner.adapter = adapter_llm

        llmModelSpinner.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>, view: View, position: Int, id: Long) {
                selectedModel = parent.getItemAtPosition(position).toString()
                Toast.makeText(this@MainActivity, "Selected: $selectedModel", Toast.LENGTH_SHORT).show()
            }

            override fun onNothingSelected(parent: AdapterView<*>) {}
        }

        llmModelSpinner.setOnTouchListener { view, event ->
            if (event.action == MotionEvent.ACTION_DOWN) {
                getModels(selectedApiEndpoint, selectedApiKey)
                view.performClick()
            }
            false
        }

        apiKeyEditText.setOnEditorActionListener { _, actionId, _ ->
            if (actionId == EditorInfo.IME_ACTION_DONE) {
                selectedApiKey = apiKeyEditText.text.toString()
                true
            } else {
                false
            }
        }

        //setup recycler view
        messageAdapter = MessageAdapter(messageList)
        recyclerView.setAdapter(messageAdapter)
        val llm: LinearLayoutManager = LinearLayoutManager(this)
        llm.setStackFromEnd(true)
        recyclerView.setLayoutManager(llm)

        sendButton.setOnClickListener(android.view.View.OnClickListener { v: android.view.View? ->
            val api_key: String = apiKeyEditText.getText().toString().trim { it <= ' ' }
            val question: String = messageEditText.getText().toString().trim { it <= ' ' }
            addToChat(question, Message.SENT_BY_ME)
            messageEditText.setText("")
            callAPI(question, api_key)
            getModels(selectedApiEndpoint, selectedApiKey)
            welcomeTextView!!.visibility = android.view.View.GONE
        })
    }

    fun addToChat(message: String, sentBy: String) {
        runOnUiThread(Runnable {
            messageList!!.add(Message(message, sentBy))
            messageAdapter!!.notifyDataSetChanged()
            recyclerView.smoothScrollToPosition(messageAdapter!!.itemCount)
        })
    }

    fun addResponse(response: String) {
        messageList!!.removeAt(messageList!!.size - 1)
        addToChat(response, Message.SENT_BY_PG)
    }

    fun callAPI(question: String?, apiKey: String?) {
        if (question.isNullOrBlank()) {
            addResponse("Question cannot be empty.")
            return
        }

        messageList.add(Message("Typing...", Message.SENT_BY_PG))

        val jsonBody = JSONObject().apply {
            put("model", selectedModel)
            put("stream", false)

            val messages = JSONArray().apply {
                put(JSONObject().apply {
                    put("role", "System")
                    put("content", "You are a helpful assistant.")
                })
                put(JSONObject().apply {
                    put("role", "User")
                    put("content", question)
                })
            }

            put("messages", messages)
        }

        val mediaType = "application/json".toMediaType()
        val requestBody = jsonBody.toString().toRequestBody(mediaType)

        val request = Request.Builder()
            .url(selectedApiEndpoint + "/chat/completions")
            .header("Content-Type", "application/json")
            .header("Authorization", "Bearer " + selectedApiKey) // Replace with secure token handling
            .post(requestBody)
            .build()

        val client = OkHttpClient()

        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                addResponse("Failed to load response: ${e.message}")
            }

            override fun onResponse(call: Call, response: Response) {
                response.use {
                    if (!it.isSuccessful) {
                        addResponse("Failed to load response: ${it.body?.string()}")
                        return
                    }

                    try {
                        val json = JSONObject(it.body?.string() ?: "")
                        val content = json.getJSONArray("choices")
                            .getJSONObject(0)
                            .getJSONObject("message")
                            .getString("content")
                        addResponse(content.trim())
                    } catch (e: JSONException) {
                        addResponse("Error parsing response: ${e.message}")
                    }
                }
            }
        })
    }
    fun getModels(endPoint: String?, apiKey: String?) {

        val request = Request.Builder()
            .url(selectedApiEndpoint + "/models")
            .get()
            .addHeader("Authorization", "Bearer " + selectedApiKey)
            .build()

        val client = OkHttpClient()

        try {
            client.newCall(request).enqueue(object : Callback {
                override fun onFailure(call: Call, e: IOException) {
                    addResponse("Failed to load response: ${e.message}")
                }

                override fun onResponse(call: Call, response: Response) {
                    response.use {
                        if (!it.isSuccessful) {
                            addResponse("Failed to load response: ${it.body?.string()}")
                            return
                        }

                        val json = JSONObject(it.body?.string() ?: "")
                        val modelList = json.getJSONArray("llm")
                        llmModels.clear()
                        llmModels.addAll(
                            List(modelList.length()) { i -> modelList.getString(i) }
                        )
                    }
                }
            })
        } catch (e: JSONException) {
            // Do Nothing
        }
    }
}
