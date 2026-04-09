import 'package:flutter/material.dart';
import 'package:product_app/screens/copilot_chat_screen.dart';

class CopilotButton extends StatelessWidget {
  const CopilotButton({super.key});

  @override
  Widget build(BuildContext context) {
    return FloatingActionButton(
      onPressed: () {
        Navigator.push(
        context,
        MaterialPageRoute(builder: (context) => CopilotChatScreen()),
      );
    },
    child: Icon(Icons.smart_toy),
    );
  }
}