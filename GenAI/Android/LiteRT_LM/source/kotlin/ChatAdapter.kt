/*
 *===--ChatAdapter.kt---------------------------------------------------===//
 * Part of the Startup-Demos Project, under the MIT License
 * See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
 * for license information.
 * Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
 * SPDX-License-Identifier: MIT
 *===----------------------------------------------------------------------===//
 */

package com.example.litertlm

import android.view.LayoutInflater
import android.view.ViewGroup
import android.widget.FrameLayout
import android.widget.TextView
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.RecyclerView

class ChatAdapter(messages: List<ChatMessage>) : RecyclerView.Adapter<ChatAdapter.MessageViewHolder>() {
    private val messages = messages.toMutableList()
    
    class MessageViewHolder(val container: FrameLayout) : RecyclerView.ViewHolder(container) {
        private val textView: TextView = container.findViewById(R.id.messageText)
        
        fun bind(message: ChatMessage) {
            textView.text = message.text
            
            val params = textView.layoutParams as FrameLayout.LayoutParams
            val context = container.context
            
            when (message.role) {
                "user" -> {
                    textView.setBackgroundColor(ContextCompat.getColor(context, R.color.litertlm_user_message_bg))
                    textView.setTextColor(ContextCompat.getColor(context, R.color.litertlm_user_message_text))
                    params.gravity = android.view.Gravity.END
                }
                "model" -> {
                    textView.setBackgroundColor(ContextCompat.getColor(context, R.color.litertlm_model_message_bg))
                    textView.setTextColor(ContextCompat.getColor(context, R.color.litertlm_model_message_text))
                    params.gravity = android.view.Gravity.START
                }
            }
            
            textView.layoutParams = params
        }
    }
    
    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): MessageViewHolder {
        val view = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_chat_message, parent, false) as FrameLayout
        return MessageViewHolder(view)
    }
    
    override fun onBindViewHolder(holder: MessageViewHolder, position: Int) {
        holder.bind(messages[position])
    }

    fun updateMessages(newMessages: List<ChatMessage>) {
        if (newMessages == messages) {
            return
        }

        when {
            newMessages.size == messages.size + 1 && newMessages.subList(0, messages.size) == messages -> {
                messages.add(newMessages.last())
                notifyItemInserted(messages.lastIndex)
            }
            newMessages.size == messages.size &&
                messages.isNotEmpty() &&
                newMessages.dropLast(1) == messages.dropLast(1) -> {
                val lastIndex = messages.lastIndex
                if (messages[lastIndex] != newMessages[lastIndex]) {
                    messages[lastIndex] = newMessages[lastIndex]
                    notifyItemChanged(lastIndex)
                }
            }
            else -> {
                messages.clear()
                messages.addAll(newMessages)
                notifyDataSetChanged()
            }
        }
    }
    
    override fun getItemCount() = messages.size
}
