package com.example.inferencecloudchat

class Message(@JvmField var message: String, @JvmField var sentBy: String) {
    companion object {
        @JvmField
        var SENT_BY_ME: String = "me"
        var SENT_BY_PG: String = "bot"
    }
}
