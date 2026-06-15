import { View, Text } from '@tarojs/components';
import { useLoad } from '@tarojs/taro';

export default function IndexPage() {
  useLoad(() => {
    console.log('Page loaded.');
  });

  return (
    <View>
      <Text>足球舆情分销系统</Text>
    </View>
  );
}
