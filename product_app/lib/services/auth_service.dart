import 'dart:convert';
import 'package:http/http.dart' as http;

/// ✅ Result object returned after successful login
class AuthResult {
  final String userId;   // ✅ required for recommendations
  final String token;
  final String username;
  final String role;     // ✅ NEW (admin / user)

  AuthResult({
    required this.userId,
    required this.token,
    required this.username,
    required this.role,
  });
}

class AuthService {
  static const String baseUrl = "http://10.0.2.2:8000";

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
  // ✅ LOGIN (UPDATED FOR ROLE)
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
      final String? userId = data["user_id"];
      final String username =
          data["username"] ?? "User"; // ✅ FIXED KEY
      final String role =
          data["role"] ?? "user";     // ✅ NEW

      // ✅ STRICT VALIDATION
      if (token == null || userId == null) {
        return null;
      }

      return AuthResult(
        userId: userId,
        token: token,
        username: username,
        role: role,
      );
    } catch (e) {
      print("LOGIN ERROR: $e");
      return null;
    }
  }

  static Future<Map<String, dynamic>?> getUserProfile(String userId) async {
    final response = await http.get(
      Uri.parse("http://10.0.2.2:8000/users/$userId"),
    );

    if (response.statusCode != 200) return null;

    return jsonDecode(response.body);
  }

}