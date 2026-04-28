import 'package:flutter/material.dart';

class CopilotButton extends StatelessWidget {
  final VoidCallback onTap;

  const CopilotButton({super.key, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return FloatingActionButton(
      backgroundColor: Colors.blue, // ✅ changed to blue
      onPressed: onTap,
      child: const Icon(
        Icons.auto_awesome,
        color: Colors.white, // ✅ good contrast
      ),
    );
  }
}
