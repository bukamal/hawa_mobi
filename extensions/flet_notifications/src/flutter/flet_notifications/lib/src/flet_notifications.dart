import 'dart:convert';
import 'package:flet/flet.dart';
import 'package:flutter/material.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:timezone/data/latest.dart' as tz_data;
import 'package:timezone/timezone.dart' as tz;

class NotificationActionData {
  final String id;
  final String title;
  final bool destructive;
  final bool foreground;
  const NotificationActionData(this.id, this.title, this.destructive, this.foreground);
}

class NotificationService {
  NotificationService._();
  static final NotificationService instance = NotificationService._();
  final FlutterLocalNotificationsPlugin plugin = FlutterLocalNotificationsPlugin();
  bool initialized = false;
  void Function(String, String)? onAction;

  Future<void> initialize() async {
    if (initialized) return;
    tz_data.initializeTimeZones();
    const android = AndroidInitializationSettings('@mipmap/ic_launcher');
    const darwin = DarwinInitializationSettings();
    await plugin.initialize(
      const InitializationSettings(android: android, iOS: darwin, macOS: darwin),
      onDidReceiveNotificationResponse: (response) {
        onAction?.call(response.actionId ?? 'tap', response.payload ?? '');
      },
    );
    initialized = true;
  }

  Importance importance(String value) {
    switch (value) {
      case 'max': return Importance.max;
      case 'high': return Importance.high;
      case 'low': return Importance.low;
      case 'min': return Importance.min;
      default: return Importance.defaultImportance;
    }
  }

  Priority priority(String value) {
    switch (value) {
      case 'max': return Priority.max;
      case 'high': return Priority.high;
      case 'low': return Priority.low;
      case 'min': return Priority.min;
      default: return Priority.defaultPriority;
    }
  }

  NotificationVisibility visibility(String value) {
    switch (value) {
      case 'public': return NotificationVisibility.public;
      case 'secret': return NotificationVisibility.secret;
      default: return NotificationVisibility.private;
    }
  }

  List<AndroidNotificationAction> androidActions(List<NotificationActionData> actions) =>
      actions.map((a) => AndroidNotificationAction(
        a.id,
        a.title,
        showsUserInterface: a.foreground,
        cancelNotification: true,
      )).toList();

  NotificationDetails details(Map<String, String> args, List<NotificationActionData> actions) {
    final level = args['importance'] ?? 'default';
    final body = args['body'] ?? '';
    return NotificationDetails(
      android: AndroidNotificationDetails(
        args['channel_id'] ?? 'hawaa_due_soon',
        args['channel_name'] ?? 'استحقاقات قريبة',
        channelDescription: args['channel_description'] ?? 'تنبيهات هواء',
        importance: importance(level),
        priority: priority(level),
        visibility: visibility(args['privacy'] ?? 'private'),
        category: AndroidNotificationCategory.reminder,
        groupKey: args['group_key'] ?? 'hawaa_payments',
        styleInformation: BigTextStyleInformation(body),
        actions: androidActions(actions),
        playSound: level == 'high' || level == 'max',
        enableVibration: level == 'high' || level == 'max',
        autoCancel: true,
      ),
      iOS: const DarwinNotificationDetails(categoryIdentifier: 'hawaa_payment'),
      macOS: const DarwinNotificationDetails(categoryIdentifier: 'hawaa_payment'),
    );
  }

  Future<bool> permissions() async {
    await initialize();
    final android = await plugin
        .resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>()
        ?.requestNotificationsPermission();
    final ios = await plugin
        .resolvePlatformSpecificImplementation<IOSFlutterLocalNotificationsPlugin>()
        ?.requestPermissions(alert: true, badge: true, sound: true);
    return ios ?? android ?? true;
  }

  Future<bool> enabled() async {
    await initialize();
    return await plugin
        .resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>()
        ?.areNotificationsEnabled() ?? true;
  }
}

class FletNotificationsControl extends StatefulWidget {
  final Control? parent;
  final Control control;
  final List<Control> children;
  final FletControlBackend backend;
  const FletNotificationsControl({
    super.key,
    required this.parent,
    required this.control,
    required this.children,
    required this.backend,
  });
  @override
  State<FletNotificationsControl> createState() => _FletNotificationsControlState();
}

class _FletNotificationsControlState extends State<FletNotificationsControl> {
  final service = NotificationService.instance;

  @override
  void initState() {
    super.initState();
    service.initialize().then((_) {
      service.onAction = (actionId, payload) {
        widget.backend.triggerControlEvent(
          widget.control.id,
          'notification_action',
          jsonEncode({'actionId': actionId, 'payload': payload}),
        );
      };
    });
    widget.backend.subscribeMethods(widget.control.id, handleMethod);
  }

  List<NotificationActionData> parseActions(String? raw) {
    if (raw == null || raw.isEmpty) return const [];
    try {
      final list = jsonDecode(raw) as List<dynamic>;
      return list.map((item) {
        final map = Map<String, dynamic>.from(item as Map);
        return NotificationActionData(
          map['id']?.toString() ?? 'open',
          map['title']?.toString() ?? 'فتح',
          map['destructive'] == true,
          map['foreground'] != false,
        );
      }).toList();
    } catch (_) {
      return const [];
    }
  }

  Future<String?> handleMethod(String method, Map<String, String> args) async {
    try {
      await service.initialize();
      final id = int.tryParse(args['id'] ?? '') ?? 0;
      final actions = parseActions(args['actions']);
      switch (method) {
        case 'initialize':
          return 'ok';
        case 'show_notification':
          await service.plugin.show(
            id, args['title'], args['body'], service.details(args, actions),
            payload: args['payload'],
          );
          return 'ok';
        case 'schedule_notification':
          final value = DateTime.parse(args['scheduled_date'] ?? '');
          await service.plugin.zonedSchedule(
            id, args['title'], args['body'],
            tz.TZDateTime.from(value, tz.local),
            service.details(args, actions),
            androidScheduleMode: AndroidScheduleMode.inexactAllowWhileIdle,
            payload: args['payload'],
          );
          return 'ok';
        case 'cancel':
          await service.plugin.cancel(id);
          return 'ok';
        case 'cancel_all':
          await service.plugin.cancelAll();
          return 'ok';
        case 'request_permissions':
          return (await service.permissions()).toString();
        case 'are_notifications_enabled':
          return (await service.enabled()).toString();
        case 'pending_notifications':
          final pending = await service.plugin.pendingNotificationRequests();
          return jsonEncode(pending.map((p) => {
            'id': p.id, 'title': p.title, 'body': p.body, 'payload': p.payload,
          }).toList());
        case 'active_notifications':
          final active = await service.plugin.getActiveNotifications();
          return jsonEncode(active.map((p) => {
            'id': p.id, 'title': p.title, 'body': p.body, 'payload': p.payload,
          }).toList());
        case 'launch_details':
          final details = await service.plugin.getNotificationAppLaunchDetails();
          final response = details?.notificationResponse;
          return jsonEncode({
            'didLaunch': details?.didNotificationLaunchApp ?? false,
            'actionId': response?.actionId ?? 'tap',
            'payload': response?.payload ?? '',
            'id': response?.id,
          });
        default:
          return null;
      }
    } catch (error) {
      debugPrint('flet_notifications error: $method $error');
      return 'error:$error';
    }
  }

  @override
  void dispose() {
    widget.backend.unsubscribeMethods(widget.control.id);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => const SizedBox.shrink();
}
