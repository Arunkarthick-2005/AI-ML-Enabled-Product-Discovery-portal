import 'package:flutter/material.dart';

class AuthTextField extends StatelessWidget {
  final String label;
  final TextEditingController controller;
  final bool isPassword;
  final IconData? prefixIcon;

  const AuthTextField({
    super.key,
    required this.label,
    required this.controller,
    this.isPassword = false,
    this.prefixIcon,
  });

  @override
Widget build(BuildContext context) {
  return SizedBox(
    width: 320, // ✅ fixed length
    child: Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: TextField(
        controller: controller,
        obscureText: isPassword,
        style: const TextStyle(fontSize: 14),
        decoration: InputDecoration(
          labelText: label,
          isDense: true,
          contentPadding: const EdgeInsets.symmetric(
            vertical: 12,
            horizontal: 12,
          ),
          prefixIcon: prefixIcon != null
              ? Icon(prefixIcon, size: 20)
              : null,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(10),
          ),
        ),
      ),
    ),
  );
}
}