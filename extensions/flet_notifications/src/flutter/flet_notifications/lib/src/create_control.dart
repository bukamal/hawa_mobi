import 'package:flet/flet.dart';
import 'flet_notifications.dart';

CreateControlFactory createControl = (CreateControlArgs args) {
  switch (args.control.type) {
    case "flet_notifications":
      return FletNotificationsControl(
        parent: args.parent,
        control: args.control,
        children: args.children,
        backend: args.backend,
      );
    default:
      return null;
  }
};

void ensureInitialized() {}
