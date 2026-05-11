import 'dart:convert';
import 'package:http/http.dart' as http;

/// ✅ Result object returned after successful login
class AuthResult {
  final String userId;   // ✅ REQUIRED for recommendations
  final String token;
  final String username;

  AuthResult({
    required this.userId,
    required this.token,
    required this.username,
  });
}

class AuthService {
  static const String baseUrl = "http://localhost:8000";

  // -----------------------------
  // ✅ REGISTER (UNCHANGED)
  // -----------------------------
  static Future<String?> register(
    String name,
    String email,
    String mobile,
    String password,
  ) async {
    try {
      final response = await http.post(
        Uri.parse("$baseUrl/auth/register"),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({
          "name": name,
          "email": email,
          "mobile": mobile,
          "password": password,
        }),
      );

      if (response.statusCode == 200 ||
          response.statusCode == 201) {
        return null;
      }

      final data = jsonDecode(response.body);
      return data["detail"] ?? "Registration failed";
    } catch (_) {
      return "Server connection error";
    }
  }

  // -----------------------------
  // ✅ LOGIN (FIXED FOR USER ID)
  // -----------------------------
  static Future<AuthResult?> login(
    String email,
    String password,
  ) async {
    try {
      final response = await http.post(
        Uri.parse("$baseUrl/auth/login"),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({
          "email": email,
          "password": password,
        }),
      );

      if (response.statusCode != 200) return null;

      final data = jsonDecode(response.body);

      final String? token = data["access_token"];
      final String? userId = data["user_id"]; // ✅ UUID from backend
      final String username =
          data["name"] ?? "User"; // display only

      // ✅ STRICT VALIDATION
      if (token == null || userId == null) {
        return null;
      }

      return AuthResult(
        userId: userId,
        token: token,
        username: username,
      );
    } catch (e) {
      print("LOGIN ERROR: $e");
      return null;
    }
  }
}