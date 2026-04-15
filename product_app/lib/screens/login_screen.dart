import 'package:flutter/material.dart';
import '../widgets/auth_text_field.dart';
import '../services/auth_service.dart';
import 'home_screen.dart';
import 'package:product_app/screens/register_screen.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final emailController = TextEditingController();
  final passwordController = TextEditingController();
  bool loading = false;

  static const double fieldWidth = 320;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF5F7FA),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            children: [
              const SizedBox(height: 40),

              const Text(
                "Welcome to the Product Discovery Portal",
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 26, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              Text("Login to continue",
                  style: TextStyle(color: Colors.grey[600])),

              const SizedBox(height: 32),

              Center(
                child: Card(
                  elevation: 6,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      children: [
                        SizedBox(
                          width: fieldWidth,
                          child: AuthTextField(
                            label: "Email",
                            controller: emailController,
                            prefixIcon: Icons.email_outlined,
                          ),
                        ),
                        const SizedBox(height: 12),
                        SizedBox(
                          width: fieldWidth,
                          child: AuthTextField(
                            label: "Password",
                            controller: passwordController,
                            isPassword: true,
                            prefixIcon: Icons.lock_outline,
                          ),
                        ),
                        const SizedBox(height: 24),

                        SizedBox(
                          width: fieldWidth,
                          height: 44,
                          child: ElevatedButton(
                            onPressed: loading
                                ? null
                                : () async {
                                    setState(() => loading = true);

                                    final result =
                                        await AuthService.login(
                                      emailController.text.trim(),
                                      passwordController.text.trim(),
                                    );

                                    setState(() => loading = false);

                                    if (result != null) {
                                      Navigator.pushReplacement(
                                        context,
                                        MaterialPageRoute(
                                          builder: (_) => HomeScreen(
                                            username: result.username,
                                          ),
                                        ),
                                      );
                                    } else {
                                      ScaffoldMessenger.of(context).showSnackBar(
                                        const SnackBar(
                                          content:
                                              Text("Invalid credentials"),
                                        ),
                                      );
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
                                : const Text("Login"),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),

              const SizedBox(height: 24),

              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text("Don’t have an account?",
                      style: TextStyle(color: Colors.grey[700])),
                  TextButton(
                    onPressed: () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => const RegisterScreen(),
                        ),
                      );
                    },
                    child: const Text("Create one"),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}