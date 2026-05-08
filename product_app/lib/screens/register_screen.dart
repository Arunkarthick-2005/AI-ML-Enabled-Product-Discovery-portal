import 'package:flutter/material.dart';
import '../services/auth_service.dart';

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key});

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final _formKey = GlobalKey<FormState>();

  final nameController = TextEditingController();
  final emailController = TextEditingController();
  final mobileController = TextEditingController();
  final passwordController = TextEditingController();

  bool loading = false;

  static const double fieldWidth = 320;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            children: [
              const SizedBox(height: 40),

              // 📝 Title
              const Text(
                "Create Account",
                style: TextStyle(
                  color : Colors.blue,
                  fontSize: 26,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                "Sign up to get started",
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),

              const SizedBox(height: 32),

              // 📦 Registration Card
              Center(
                child: Card(
                  elevation: 6,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Form(
                      key: _formKey,
                      child: Column(
                        children: [
                          // 👤 Name
                          SizedBox(
                            width: fieldWidth,
                            child: TextFormField(
                              controller: nameController,
                              decoration: _inputDecoration(
                                "Name",
                                Icons.person_outline,
                              ),
                              validator: (value) {
                                if (value == null ||
                                    value.trim().length < 3) {
                                  return "Name must be at least 3 characters";
                                }
                                return null;
                              },
                            ),
                          ),

                          const SizedBox(height: 12),

                          // 📧 Email
                          SizedBox(
                            width: fieldWidth,
                            child: TextFormField(
                              controller: emailController,
                              keyboardType: TextInputType.emailAddress,
                              decoration: _inputDecoration(
                                "Email",
                                Icons.email_outlined,
                              ),
                              validator: (value) {
                                final emailRegex = RegExp(
                                    r'^[\w-.]+@([\w-]+\.)+[\w-]{2,4}$');
                                if (value == null ||
                                    !emailRegex.hasMatch(value)) {
                                  return "Enter a valid email";
                                }
                                return null;
                              },
                            ),
                          ),

                          const SizedBox(height: 12),

                          // 📱 Mobile
                          SizedBox(
                            width: fieldWidth,
                            child: TextFormField(
                              controller: mobileController,
                              keyboardType: TextInputType.phone,
                              decoration: _inputDecoration(
                                "Mobile Number",
                                Icons.phone_outlined,
                              ),
                              validator: (value) {
                                if (value == null ||
                                    !RegExp(r'^\d{10}$').hasMatch(value)) {
                                  return "Enter valid 10-digit mobile number";
                                }
                                return null;
                              },
                            ),
                          ),

                          const SizedBox(height: 12),

                          // 🔐 Password
                          SizedBox(
                            width: fieldWidth,
                            child: TextFormField(
                              controller: passwordController,
                              obscureText: true,
                              decoration: _inputDecoration(
                                "Password",
                                Icons.lock_outline,
                              ),
                              validator: (value) {
                                if (value == null || value.length < 8) {
                                  return "Minimum 8 characters";
                                }
                                if (!RegExp(r'[A-Z]').hasMatch(value)) {
                                  return "Add one uppercase letter";
                                }
                                if (!RegExp(r'[a-z]').hasMatch(value)) {
                                  return "Add one lowercase letter";
                                }
                                if (!RegExp(r'\d').hasMatch(value)) {
                                  return "Add one number";
                                }
                                if (!RegExp(r'[!@#$%^&*(),.?":{}|<>]')
                                    .hasMatch(value)) {
                                  return "Add one special character";
                                }
                                return null;
                              },
                            ),
                          ),

                          const SizedBox(height: 24),

                          // 🔘 Register Button
                          SizedBox(
                            width: fieldWidth,
                            height: 44,
                            child: ElevatedButton(
                              style: ElevatedButton.styleFrom(
                                backgroundColor: const Color(0xFF2563EB),
                                foregroundColor: Colors.white,
                                padding: EdgeInsets.zero,
                                shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(10),
                                ),
                              ),
                              onPressed: loading
                                  ? null
                                  : () async {
                                      if (_formKey.currentState!.validate()) {
                                        setState(() => loading = true);

                                        final error =
                                            await AuthService.register(
                                          nameController.text.trim(),
                                          emailController.text.trim(),
                                          mobileController.text.trim(),
                                          passwordController.text.trim(),
                                        );

                                        setState(() => loading = false);

                                        if (error == null) {
                                          ScaffoldMessenger.of(context)
                                              .showSnackBar(
                                            const SnackBar(
                                              content: Text(
                                                  "Registration successful"),
                                            ),
                                          );
                                          Navigator.pop(context);
                                        } else {
                                          ScaffoldMessenger.of(context)
                                              .showSnackBar(
                                            SnackBar(content: Text(error)),
                                          );
                                        }
                                      }
                                    },
                              child: loading
                                  ? const SizedBox(
                                      width: 18,
                                      height: 18,
                                      child: CircularProgressIndicator(
                                        strokeWidth: 2,
                                        color: Colors.white,
                                      ),
                                    )
                                  : const Text(
                                      "Create Account",
                                      style: TextStyle(fontSize: 15),
                                    ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  /// ✅ Shared Input Decoration (keeps UI consistent)
  InputDecoration _inputDecoration(String label, IconData icon) {
    return InputDecoration(
      labelText: label,
      prefixIcon: Icon(icon, size: 20),
      isDense: true,
      contentPadding: const EdgeInsets.symmetric(
        vertical: 12,
        horizontal: 12,
      ),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(10),
      ),
    );
  }
}