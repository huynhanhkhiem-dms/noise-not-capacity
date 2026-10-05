package org.slf4j;
public interface Logger {
  default boolean isDebugEnabled(){return false;}
  default boolean isTraceEnabled(){return false;}
  default boolean isInfoEnabled(){return false;}
  default void debug(String s, Object... a){}
  default void trace(String s, Object... a){}
  default void info(String s, Object... a){}
  default void warn(String s, Object... a){}
  default void error(String s, Object... a){}
}
