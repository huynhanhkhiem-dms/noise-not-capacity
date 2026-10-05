package org.slf4j;
public final class LoggerFactory {
  private static final Logger L = new Logger(){};
  public static Logger getLogger(Class<?> c){return L;}
  public static Logger getLogger(String n){return L;}
}
