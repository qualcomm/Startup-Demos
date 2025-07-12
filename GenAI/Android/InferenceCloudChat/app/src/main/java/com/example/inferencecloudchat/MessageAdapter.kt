package com.example.inferencecloudchat

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.LinearLayout
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView
import com.example.inferencecloudchat.MessageAdapter.MyViewHolder

class MessageAdapter(var messageList: MutableList<Message>) :
    RecyclerView.Adapter<MyViewHolder>() {
    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): MyViewHolder {
        val chatView = LayoutInflater.from(parent.context).inflate(R.layout.message_view, null)
        val myViewHolder = MyViewHolder(chatView)
        return myViewHolder
    }

    override fun onBindViewHolder(holder: MyViewHolder, position: Int) {
        val message = messageList[position]
        if (message.sentBy == Message.SENT_BY_ME) {
            holder.recvMessageView.visibility = View.GONE
            holder.sendMessageView.visibility = View.VISIBLE
            holder.sendTextView.text = message.message
        } else {
            holder.sendMessageView.visibility = View.GONE
            holder.recvMessageView.visibility = View.VISIBLE
            holder.recvTextView.text = message.message
        }
    }

    override fun getItemCount(): Int {
        return messageList.size
    }

    inner class MyViewHolder(itemView: View) : RecyclerView.ViewHolder(itemView) {
        var recvMessageView: LinearLayout = itemView.findViewById(R.id.recv_message)
        var sendMessageView: LinearLayout = itemView.findViewById(R.id.send_message)
        var recvTextView: TextView =
            itemView.findViewById(R.id.recv_message_text_view)
        var sendTextView: TextView =
            itemView.findViewById(R.id.send_message_text_view)
    }
}
