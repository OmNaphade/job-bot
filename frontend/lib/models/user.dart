class User {
  final int id;
  final String email;
  final String createdAt;

  const User({required this.id, required this.email, required this.createdAt});

  factory User.fromJson(Map<String, dynamic> json) => User(
        id: json['id'] as int,
        email: json['email'] as String,
        createdAt: json['created_at'] as String? ?? '',
      );
}
