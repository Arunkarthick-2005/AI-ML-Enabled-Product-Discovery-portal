import 'package:flutter/material.dart';


class CopilotChatScreen extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text("Copilot"),
      ),
      body: Column(
        children: [
          Expanded(
            child: ListView(
              padding: EdgeInsets.all(16),
              children: [
                Text(
                  "👋 Hi! I'm Copilot.\nAsk me anything about products.",
                  style: TextStyle(fontSize: 16),
                ),
              ],
            ),
          ),
          Container(
            padding: EdgeInsets.all(12),
            child: TextField(
              enabled: false, // backend later
              decoration: InputDecoration(
                hintText: "Copilot will be enabled soon...",
                border: OutlineInputBorder(),
              ),
            ),
          )
        ],
      ),
    );
  }
}